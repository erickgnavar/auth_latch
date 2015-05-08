# coding: utf-8
from openerp import models, fields, api
from openerp.exceptions import MissingError, ValidationError, AccessDenied

from latch import latch


def _get_api(obj):
    app_id = obj.env['ir.config_parameter'].get_param('latch.app.id')
    secret_key = obj.env['ir.config_parameter'].get_param('latch.secret.key')
    if not app_id or not secret_key:
        raise MissingError('Latch application setup incomplete')
    return latch.Latch(app_id, secret_key)


def _old_get_api(obj, cr, uid):
    app_id = obj.pool['ir.config_parameter'].get_param(cr, uid, 'latch.app.id')
    secret_key = obj.pool['ir.config_parameter'].get_param(cr, uid, 'latch.secret.key')
    if not app_id or not secret_key:
        raise MissingError('Latch application setup incomplete')
    return latch.Latch(app_id, secret_key)


class User(models.Model):

    _inherit = 'res.users'

    latch_account_id = fields.Char('Latch account id')

    @api.v7
    def check_credentials(self, cr, uid, password):
        super(User, self).check_credentials(cr, uid, password)
        self._check_latch(cr, uid)

    @api.v7
    def _check_latch(self, cr, uid):
        _api = _old_get_api(self, cr, uid)
        user = self.read(cr, uid, uid, ['latch_account_id'])
        response = _api.status(user['latch_account_id'])
        # FIXME: find a better way to check by operations
        data = response.get_data()
        status = data['operations'][data['operations'].keys()[0]]['status']
        if status == 'off':
            raise AccessDenied()


class PairLatchAccountWizard(models.TransientModel):

    _name = 'pair.latch.account.wizard'

    pairing_code = fields.Char('Pairing code', required=True)

    @api.one
    def pair(self):
        _api = _get_api(self)
        response = _api.pair(self.pairing_code)
        if 'accountId' not in response.get_data():
            raise ValidationError('A problem with pairing process occurred')
        self.env.user.write({
            'latch_account_id': response.get_data()['accountId']
        })
