'''main module of emesene, does the startup and related stuff'''
#!/usr/bin/env python
# -*- coding: utf-8 -*-

#   This file is part of emesene.
#
#    Emesene is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    emesene is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with emesene; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import os
import sys
import gtk
import time
import base64
import gobject
import gettext
import optparse

import string

import utils
import debugger
import logging
log = logging.getLogger('emesene')

import e3
from e3 import msn
from e3 import jabber
from e3 import dummy
try:
    from e3 import papylib
except Exception, exc:
    papylib = None
    log.warning('Errors occurred on papyon importing: %s' % str(exc))

from pluginmanager import get_pluginmanager
import extension
import interfaces

import gui
from gui import gtkui

# fix for gstreamer --help
argv = sys.argv
sys.argv = [argv[0]]

# load translations
if os.path.exists('default.mo'):
    gettext.GNUTranslations(open('default.mo')).install()
elif os.path.exists('po/'):
    gettext.install('emesene', 'po/')
else:
    gettext.install('emesene')


class VerboseOption(object):

    def __init__(self):
        pass

    def option_register(self):
        option = optparse.Option("-v", "--verbose",
            action="count", dest="debuglevel", default=0,
            help="Enable debug in console (add another -v to show debug)")
        return option

extension.implements('option provider')(VerboseOption)
extension.get_category('option provider').activate(VerboseOption)

class Controller(object):
    '''class that handle the transition between states of the windows'''

    def __init__(self):
        '''class constructor'''
        self.window = None
        self.tray_icon = None
        self.conversations = None
        self.config = e3.common.Config()
        self.config_dir = e3.common.ConfigDir('emesene2')
        self.config_path = self.config_dir.join('config')
        self.config.load(self.config_path)

        if self.config.d_accounts is None:
            self.config.d_accounts = {}

        self.session = None
        self._parse_commandline()
        self._setup()

    def _setup(self):
        '''register core extensions'''
        extension.category_register('session', msn.Session,
                single_instance=True)
        extension.register('session', jabber.Session)
        if papylib is not None:
            extension.register('session', papylib.Session)
        extension.category_register('sound', e3.common.play_sound.play)
        extension.category_register('notification',
                e3.common.notification.notify)
        extension.category_register('history exporter',
                e3.Logger.save_logs_as_txt)

        if self.config.session is None:
            default_id = extension.get_category('session').default_id
            self.config.session = default_id
        else:
            default_id = self.config.session

        extension.set_default('session', dummy.Session)
        get_pluginmanager().scan_directory('plugins')

    def _parse_commandline(self):
        options, args = PluggableOptionParser.get_parsing()

        debugger.init(debuglevel=options.debuglevel)

    def _new_session(self):
        '''create a new session object'''

        if self.session is not None:
            self.session.quit()

        self.session = extension.get_and_instantiate('session')

        # if you add a signal here, add it on _remove_subscriptions
        signals = self.session.signals
        signals.login_succeed.subscribe(self.on_login_succeed)
        signals.login_failed.subscribe(self.on_login_failed)
        signals.contact_list_ready.subscribe(self.on_contact_list_ready)
        signals.conv_first_action.subscribe(self.on_new_conversation)
        signals.disconnected.subscribe(self.on_disconnected)

    def _remove_subscriptons(self):
        '''remove the subscriptions to signals
        '''
        signals = self.session.signals
        signals.login_succeed.unsubscribe(self.on_login_succeed)
        signals.login_failed.unsubscribe(self.on_login_failed)
        signals.contact_list_ready.unsubscribe(self.on_contact_list_ready)
        signals.conv_first_action.unsubscribe(self.on_new_conversation)
        signals.disconnected.unsubscribe(self.on_disconnected)

    def save_extensions_config(self):
        '''save the state of the extensions to the config'''
        if self.session is None:
            return

        if self.session.config.d_extensions is None:
            self.session.config.d_extensions = {}

        for name, category in extension.get_categories().iteritems():
            self.session.config.d_extensions[name] = \
                category.default_id

    def set_default_extensions_from_config(self):
        '''get the ids of the default extensions stored on config
        and set them as default on the extensions module'''

        if self.session.config.d_extensions is not None:
            for cat_name, ext_id in self.session.config\
                    .d_extensions.iteritems():
                extension.set_default_by_id(cat_name, ext_id)

    def _get_proxy_settings(self):
        '''return the values of the proxy settings as a e3.Proxy object
        initialize the values on config if not exist'''

        use_proxy = self.config.get_or_set('b_use_proxy', False)
        use_proxy_auth = self.config.get_or_set('b_use_proxy_auth', False)
        host = self.config.get_or_set('proxy_host', '')
        port = self.config.get_or_set('proxy_port', '')
        user = self.config.get_or_set('proxy_user', '')
        passwd = self.config.get_or_set('proxy_passwd', '')

        use_http = self.config.get_or_set('b_use_http', False)

        return e3.Proxy(use_proxy, host, port, use_proxy_auth, user,
            passwd)

    def _save_proxy_settings(self, proxy):
        '''save the values of the proxy settings to config'''
        self.config.b_use_proxy = proxy.use_proxy
        self.config.b_use_proxy_auth = proxy.use_auth
        self.config.proxy_host = proxy.host
        self.config.proxy_port = proxy.port
        self.config.proxy_user = proxy.user
        self.config.proxy_passwd = proxy.passwd

    def on_close(self):
        '''called on close'''
        self.close_session()

    def on_disconnected(self, reason):
        '''called when the server disconnect us'''
        dialog = extension.get_default('dialog')
        dialog.error('Session disconnected by server')
        self.close_session(False)
        self.start()

    def close_session(self, do_exit=True):
        '''close session'''
        if self.session is not None:
            self.session.quit()

        self.save_extensions_config()
        self._save_login_dimensions()

        if self.session is not None:
            self.session.save_config()
            self.session = None

        self.config.save(self.config_path)

        if self.conversations:
            self.conversations.get_parent().hide()
            self.conversations = None

        self.window.hide()
        self.window = None

        if do_exit:
            while gtk.events_pending():
                gtk.main_iteration(False)

            sys.exit(0)

    def _save_login_dimensions(self):
        '''save the dimensions of the login window
        '''
        width, height, posx, posy = self.window.get_dimensions()

        self.config.i_login_posx = posx
        self.config.i_login_posy = posy
        self.config.i_login_width = width
        self.config.i_login_height = height

    def on_login_succeed(self):
        '''callback called on login succeed'''
        self._save_login_dimensions()
        self.config.save(self.config_path)
        self.draw_main_screen()

    def draw_main_screen(self):
        '''create and populate the main screen
        '''
        # clear image cache
        utils.pixbufs = {}
        self.window.clear()
        self.tray_icon.set_main(self.session)
        image_name = self.session.config.get_or_set('image_theme', 'default')
        emote_name = self.session.config.get_or_set('emote_theme', 'default')
        sound_name = self.session.config.get_or_set('sound_theme', 'default')
        gui.theme.set_theme(image_name, emote_name, sound_name)
        self.config.save(self.config_path)
        self.set_default_extensions_from_config()

        self.window.go_main(self.session,
                self.on_new_conversation, self.on_close, self.on_disconnect)

    def on_login_failed(self, reason):
        '''callback called on login failed'''
        self._save_login_dimensions()
        self._remove_subscriptons()
        self._new_session()
        self.go_login(True)
        self.window.content.clear_all()
        self.window.content.show_error(reason)

    def on_contact_list_ready(self):
        '''callback called when the contact list is ready to be used'''
        self.window.content.contact_list.fill()

        def on_contact_added_you(responses):
            '''
            callback called when the dialog is closed
            '''
            for account in responses['accepted']:
                self.session.add_contact(account)

            for account in responses['rejected']:
                self.session.reject_contact(account)

        if self.session.contacts.pending:
            accounts = []
            for contact in self.session.contacts.pending.values():
                accounts.append((contact.account, contact.display_name))

            dialog = extension.get_default('dialog')
            dialog.contact_added_you(accounts, on_contact_added_you)

        gobject.timeout_add(500, self.session.logger.check)

    def on_preferences_changed(self, use_http, proxy, session_id):
        '''called when the preferences on login change'''
        self.config.session = session_id
        extension.set_default_by_id('session', session_id)
        self.config.b_use_http = use_http
        self._save_proxy_settings(proxy)

    def on_login_connect(self, account, session_id, proxy, use_http):
        '''called when the user press the connect button'''
        self.on_preferences_changed(use_http, proxy, session_id)
        self._save_login_dimensions()

        self.window.clear()
        self.window.go_connect(self.on_cancel_login)
        self._set_location(self.window)
        self.window.show()

        self._new_session()
        self.session.config.get_or_set('b_play_send', True)
        self.session.config.get_or_set('b_play_nudge', True)
        self.session.config.get_or_set('b_play_first_send', True)
        self.session.config.get_or_set('b_play_type', True)
        self.session.config.get_or_set('b_play_contact_online', True)
        self.session.config.get_or_set('b_play_contact_offline', True)
        self.session.config.get_or_set('b_notify_contact_online', True)
        self.session.config.get_or_set('b_notify_contact_offline', True)
        self.session.config.get_or_set('b_show_userpanel', True)
        self.session.config.get_or_set('b_show_emoticons', True)
        self.session.config.get_or_set('b_show_header', True)
        self.session.config.get_or_set('b_show_info', True)
        self.session.config.get_or_set('b_show_toolbar', True)
        self.session.config.get_or_set('b_allow_auto_scroll', True)
        self.session.login(account.account, account.password, account.status,
            proxy, use_http)
        gobject.timeout_add(500, self.session.signals._handle_events)

    def on_new_conversation(self, cid, members, other_started=True):
        '''callback called when the other user does an action that justify
        opening a conversation'''
        if self.conversations is None:
            Window = extension.get_default('window frame')
            window = Window(self._on_conversation_window_close)

            window.go_conversation(self.session)
            self._set_location(window, True)
            self.conversations = window.content
            window.show()

        (exists, conversation) = self.conversations.new_conversation(cid,
            members)

        conversation.update_data()

        # the following lines (up to and including the second show() )
        # do 2 things:
        # a) make sure proper tab is selected (if multiple tabs are opened)
        #    when clicking on a user icon
        # b) place cursor on text box
        # both the show() calls are needed - won't work otherwise

        conversation.show() # puts widget visible

        # conversation widget MUST be visible (cf. previous line)
        self.conversations.set_current_page(conversation.tab_index)

        # raises the container (tabbed windows) if its minimized
        self.conversations.get_parent().present()

        conversation.show() # puts cursor in textbox

        play = extension.get_default('sound')
        if other_started and \
            self.session.contacts.me.status != e3.status.BUSY and \
            self.session.config.b_play_first_send:

            play(gui.theme.sound_send)

        return (exists, conversation)

    def _on_conversation_window_close(self):
        '''method called when the conversation window is closed'''
        width, height, posx, posy = \
                self.conversations.get_parent().get_dimensions()
        self.session.config.i_conv_width = width
        self.session.config.i_conv_height = height
        self.session.config.i_conv_posx = posx
        self.session.config.i_conv_posy = posy

        self.conversations.close_all()
        self.conversations = None

    def start(self, account=None, accounts=None, on_disconnect=False):
        '''the entry point to the class'''
        Window = extension.get_default('window frame')
        self.window = Window(None) # main window

        if self.tray_icon is not None:
            self.tray_icon.set_visible(False)

        TrayIcon = extension.get_default('tray icon')
        handler = gui.base.TrayIconHandler(self.session, gui.theme,
            self.on_disconnect, self.on_close)
        self.tray_icon = TrayIcon(handler, self.window)

        proxy = self._get_proxy_settings()
        use_http = self.config.get_or_set('b_use_http', False)
        account = self.config.get_or_set('last_logged_account', '')
        
        #autologin
        if account != '' and int(self.config.d_remembers[account]) == 3 \
            and not on_disconnect:
            password = base64.b64decode(self.config.d_accounts[account])
            user = e3.Account(account, password,
                              int(self.config.d_status[account]))
            self.on_login_connect(user, self.config.session, proxy, use_http)
        else:
            self.go_login(on_disconnect, proxy, use_http)

    def go_login(self, on_disconnect=False, proxy=None, use_http=None):
        '''start the login GUI'''
        if proxy is None:
            proxy = self._get_proxy_settings()
        if use_http is None:
            use_http = self.config.get_or_set('b_use_http', False)

        if self.window.content_type != 'empty':
            self.window.clear()

        self.window.go_login(self.on_login_connect,
            self.on_preferences_changed,self.config,
            self.config_dir, self.config_path, proxy,
            use_http, self.config.session, on_disconnect)
        self.tray_icon.set_login()
        self._set_location(self.window)
        self.window.show()

    def on_disconnect(self):
        '''
        method called when the user selects disconnect
        '''
        self.close_session(False)
        self.start(on_disconnect=True)
    
    def on_cancel_login(self):
        '''
        method called when user select cancel login
        '''
        if self.session is not None:
            self.session.quit()
        self._save_login_dimensions()
        self.go_login(True)

    def _set_location(self, window, is_conv=False):
        '''get and set the location of the window'''
        if is_conv:
            posx = self.session.config.get_or_set('i_conv_posx', 100)
            posy = self.session.config.get_or_set('i_conv_posy', 100)
            width = self.session.config.get_or_set('i_conv_width', 600)
            height = self.session.config.get_or_set('i_conv_height', 400)
        else:
            posx = self.config.get_or_set('i_login_posx', 100)
            posy = self.config.get_or_set('i_login_posy', 100)
            width = self.config.get_or_set('i_login_width', 250)
            height = self.config.get_or_set('i_login_height', 410)

        window.set_location(width, height, posx, posy)
        
class ExtensionDefault(object):

    def __init__(self):
        pass

    def option_register(self):
        option = optparse.Option('--ext-default', '-e')
        option.type = 'string' #well, it's a extName:defaultValue string
        option.action = 'callback'
        option.callback = self.set_default
        option.help = 'Set the default extension by name'
        option.nargs = 1
        return option

    def set_default(self, option, opt, value, parser):
        for couple in value.split(';'):
            (category_name, ext_name) = map(string.strip, couple.split(':', 2))
            if not extension.get_category(category_name)\
                    .set_default_by_name(ext_name):
                print 'Error setting extension "%s" default session to "%s"'\
                        % (category_name, ext_name)

extension.implements('option provider')(ExtensionDefault)
extension.get_category('option provider').activate(ExtensionDefault)


class PluggableOptionParser(object):

    results = ()

    def __init__(self, args):
        self.parser = optparse.OptionParser(conflict_handler="resolve")
        self.args = args
        custom_options = extension.get_category('option provider').use()()\
                .option_register().get_result()
        for opt in custom_options.values():
            self.parser.add_option(opt)

    def read_options(self):
        if not self.__class__.results:
            self.__class__.results = self.parser.parse_args(self.args)
        return self.__class__.results

    @classmethod
    def get_parsing(cls):
        return cls.results


def main():
    global argv
    """
    the main method of emesene
    """
    extension.category_register('session', msn.Session, single_instance=True)
    extension.category_register('option provider', None,
            interfaces=interfaces.IOptionProvider)
    extension.get_category('option provider').multi_extension = True
    extension.get_category('option provider').activate(ExtensionDefault)
    options = PluggableOptionParser(argv)
    options.read_options()
    main_method = extension.get_default('main')
    main_method(Controller)

if __name__ == "__main__":
    main()
