# -*- coding: utf-8 -*-
# Copyright (C) 2016-Today: La Louve (<http://www.lalouve.fr/>)
# @author: La Louve
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html

from openerp import models, fields, api, _
import logging
import random
_logger = logging.getLogger(__name__)
from openerp.exceptions import ValidationError

try:
    from validate_email import validate_email
except ImportError:
    _logger.debug("Cannot import `validate_email`.")


def random_token():
    # the token has an entropy of about 120 bits (6 bits/char * 20 chars)
    chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
    return ''.join(random.SystemRandom().choice(chars) for i in xrange(20))


class ResPartner(models.Model):
    _inherit = 'res.partner'

    email_validation_string = fields.Char(
        string="String Validation Email",
        compute="compute_hash_validation_email",
        store=True)
    is_checked_email = fields.Boolean('Is Checked Email', default=False)
    validation_url = fields.Char('Link to validate',
                                 compute="compute_url_validation_email")

    @api.multi
    def write(self, vals):
        res = super(ResPartner, self).write(vals)
        if 'email' in vals:
            for partner in self:
                partner.check_exist_email()
                if partner.validation_url and\
                        (partner.is_interested_people or partner.is_member):
                    mail_template = self.env.ref(
                        'email_validation_check.email_confirm_validate')
                    if mail_template:
                        mail_template.send_mail(self.id)

                # Update login user which's related partner
                if partner.email:
                    partner.is_checked_email = False
                    user_related = self.env['res.users'].search([
                        ('partner_id', '=', partner.id)
                    ])
                    user_related.write({
                        'login': partner.email
                    })
        return res

    @api.model
    def create(self, vals):
        res = super(ResPartner, self).create(vals)
        res.check_exist_email()
        if res.validation_url and res.is_interested_people and res.email:
            mail_template = self.env.ref(
                'email_validation_check.email_confirm_validate')
            if mail_template:
                mail_template.send_mail(res.id)
        return res

    @api.multi
    def check_exist_email(self):
        for partner in self:
            already_email = self.env['res.partner'].search([
                ('email', '=', partner.email),
                ('id', '!=', partner.id)
            ])
            if already_email:
                raise ValidationError(
                    _("Another user is already registered" +
                      " using this email address."))

    @api.multi
    @api.depends('email')
    def compute_hash_validation_email(self):
        for partner in self:
            if partner.email:
                partner.email_validation_string = random_token()
        return True

    @api.multi
    def check_email_validation_string(self, string):
        for partner in self:
            if partner.email_validation_string == string:
                partner.is_checked_email = True
                return True
            else:
                return False

    @api.multi
    def recompute_hash_confirm_email(self):
        for partner in self:
            curr_hash = partner.email_validation_string
            partner.email_validation_string = random_token()
            if partner.email_validation_string != curr_hash:
                mail_template = self.env.ref(
                    'email_validation_check.email_confirm_validate')
                if mail_template:
                    mail_template.send_mail(self.id)
        return True

    @api.multi
    @api.depends('email_validation_string')
    def compute_url_validation_email(self):
        for partner in self:
            base_url = self.env['ir.config_parameter'].get_param(
                'web.base.url')
            validation_url = base_url + '/validate' + \
                '/%s' % (partner.id) + \
                '/%s' % (partner.email_validation_string)
            partner.validation_url = validation_url