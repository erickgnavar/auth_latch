# coding: utf-8
import logging

from openerp import models, fields, api
from openerp.exceptions import ValidationError, AccessDenied

from latch import latch


_logger = logging.getLogger(__name__)


def _get_api(obj):
    app_id = obj.env['ir.config_parameter'].get_param('latch.app.id')
    secret_key = obj.env['ir.config_parameter'].get_param('latch.secret.key')
    if not app_id or not secret_key:
        _logger.warning('Latch setup incomplete, please fill the config parameters')
        return False
    return latch.Latch(app_id, secret_key)


def _old_get_api(obj, cr, uid):
    app_id = obj.pool['ir.config_parameter'].get_param(cr, uid, 'latch.app.id')
    secret_key = obj.pool['ir.config_parameter'].get_param(cr, uid, 'latch.secret.key')
    if not app_id or not secret_key:
        return False
    return latch.Latch(app_id, secret_key)


class User(models.Model):

    _inherit = 'res.users'

    latch_account_id = fields.Char('Latch account id')
    latch_paired = fields.Boolean(default=False)

    @api.v7
    def check_credentials(self, cr, uid, password):
        super(User, self).check_credentials(cr, uid, password)
        self._check_latch(cr, uid)

    @api.v7
    def _check_latch(self, cr, uid):
        _api = _old_get_api(self, cr, uid)
        if not _api:
            return
        user = self.read(cr, uid, uid, ['latch_paired', 'latch_account_id'])
        if not user['latch_account_id'] or not user['latch_account_id']:
            return
        response = _api.status(user['latch_account_id'])
        if not response.get_data():
            return
        # FIXME: find a better way to check by operations
        data = response.get_data()
        status = data['operations'][data['operations'].keys()[0]]['status']
        if status == 'off':
            raise AccessDenied()

    @api.one
    def latch_unpair(self):
        _api = _get_api(self)
        if not _api:
            return
        _api.unpair(self.latch_account_id)
        self.env.user.write({
            'latch_account_id': '',
            'latch_paired': False
        })


class PairLatchAccountWizard(models.TransientModel):

    _name = 'pair.latch.account.wizard'

    pairing_code = fields.Char('Pairing code', required=True)

    @api.one
    def pair(self):
        _api = _get_api(self)
        if not _api:
            return
        response = _api.pair(self.pairing_code)
        if not response.get_data():
            raise ValidationError('Wrong pair code')
        if 'accountId' not in response.get_data():
            raise ValidationError('A problem with pairing process occurred')
        self.env.user.write({
            'latch_account_id': response.get_data()['accountId'],
            'latch_paired': True
        })
