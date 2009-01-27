import gtk

import RichBuffer
import e3common.MarkupParser

class TextBox(gtk.ScrolledWindow):
    '''a text box inside a scroll that provides methods to get and set the
    text in the widget'''

    def __init__(self, config):
        '''constructor'''
        gtk.ScrolledWindow.__init__(self)

        self.config = config

        if self.config.b_show_emoticons is None:
            self.config.b_show_emoticons = True

        self.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.set_shadow_type(gtk.SHADOW_IN)
        self._textbox = gtk.TextView()
        self._textbox.set_left_margin(6)
        self._textbox.set_right_margin(6)
        self._textbox.set_wrap_mode(gtk.WRAP_WORD_CHAR)
        self._textbox.show()
        self._buffer = RichBuffer.RichBuffer()
        self._textbox.set_buffer(self._buffer)
        self.add(self._textbox)

    def clear(self):
        '''clear the content'''
        self._buffer.set_text('')

    def _append(self, text, scroll=True, fg_color=None, bg_color=None,
        font=None, size=None, bold=False, italic=False, underline=False,
        strike=False):
        '''append text to the widget'''
        self._buffer.put_text(text, fg_color, bg_color, font, size, bold,
            italic, underline, strike)

        if scroll:
            self.scroll_to_end()

    def append(self, text, scroll=True):
        '''append formatted text to the widget'''
        if self.config.b_show_emoticons:
            text = e3common.MarkupParser.parse_emotes(text)

        self._buffer.put_formatted(text)
        [self._textbox.add_child_at_anchor(*item)
            for item in self._buffer.widgets]

        self._buffer.widgets = []

        if scroll:
            self.scroll_to_end()

    def scroll_to_end(self):
        '''scroll to the end of the content'''
        end_iter = self._buffer.get_end_iter()
        self._textbox.scroll_to_iter(end_iter, 0.0, yalign=1.0)

    def _set_text(self, text):
        '''set the text on the widget'''
        self._buffer.set_text(text)

    def _get_text(self):
        '''return the text of the widget'''
        start_iter = self._buffer.get_start_iter()
        end_iter = self._buffer.get_end_iter()
        return self._buffer.get_text(start_iter, end_iter, True)

    text = property(fget=_get_text, fset=_set_text)

class InputText(TextBox):
    '''a widget that is used to insert the messages to send'''

    def __init__(self, config, on_send_message):
        '''constructor'''
        TextBox.__init__(self, config)
        self.on_send_message = on_send_message
        self._textbox.connect('key-press-event', self._on_key_press_event)

    def _on_key_press_event(self, widget, event):
        '''method called when a key is pressed on the input widget'''
        if event.keyval == gtk.keysyms.Return and \
                not event.state == gtk.gdk.SHIFT_MASK:
            if not self.text:
                return True

            self.on_send_message(self.text)
            self.text = ''
            return True

class OutputText(TextBox):
    '''a widget that is used to display the messages on the conversation'''

    def __init__(self, config):
        '''constructor'''
        TextBox.__init__(self, config)
        self._textbox.set_editable(False)
        self._textbox.set_cursor_visible(False)