''' a gtk widget for managing file transfers '''
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

import gtk
import pango
import gobject

class FtBarWidget(gtk.HBox):
    '''bar which represents active file transfers'''
    def __init__(self):
        gtk.HBox.__init__(self)

        self.set_spacing(3)

        self.hbox = gtk.HBox()
        self.hbox.set_spacing(3)

        self.layout = gtk.Layout()
        self.layout.put(self.hbox, 0, 0)
        self.layout.set_size(self.hbox.get_allocation().width, \
                               self.hbox.get_allocation().height + 100)

        self.current = 0
        self.speed = 5
        self.page = 0
        self.twidth = 150
        self.num_transfers = 0
        self.dest = 0
        self.div = 0
        self.new_transfer_bar = None

        arrow_left = gtk.Arrow(gtk.ARROW_LEFT, gtk.SHADOW_IN)
        arrow_right = gtk.Arrow(gtk.ARROW_RIGHT, gtk.SHADOW_IN)
        self.b_go_left = gtk.Button()
        self.b_go_left.add(arrow_left)
        self.b_go_left.set_sensitive(False)
        self.b_go_left.set_relief(gtk.RELIEF_NONE)
        self.b_go_left.connect('clicked', self._on_left_button_clicked)

        self.b_go_right = gtk.Button()
        self.b_go_right.add(arrow_right)
        self.b_go_right.set_sensitive(False)
        self.b_go_right.set_relief(gtk.RELIEF_NONE)
        self.b_go_right.connect('clicked', self._on_right_button_clicked)

        self.pack_start(self.b_go_left, False, False)
        self.pack_start(self.layout)
        self.pack_start(self.b_go_right, False, False)


    def add(self, transfer):
        ''' add a new transfer to the widget '''
        self.new_transfer_bar = FtWidget(self, transfer)
        self.hbox.pack_start(self.new_transfer_bar, False, False)
        self.num_transfers += 1
        if self.num_transfers > 1:
            self.b_go_right.set_sensitive(True)
        else:
            self.b_go_right.set_sensitive(False)
        self.set_no_show_all(False)
        self.show_all()

    def _on_left_button_clicked(self, widget):
        ''' when the user click on the go-left button '''
        self.twidth = self.new_transfer_bar.get_allocation().width
        self.page -= 1
        self.dest = -self.twidth * self.page
        gobject.timeout_add(5, self._move_to_left)

    def _on_right_button_clicked(self, widget):
        ''' when the user click on the go-right button '''
        if self.num_transfers == 1: 
            self.b_go_right.set_sensitive(False)
            return False
        self.twidth = self.new_transfer_bar.get_allocation().width
        self.b_go_left.set_sensitive(True)
        self.page += 1
        self.dest = -self.twidth * self.page
        gobject.timeout_add(5, self._move_to_right)

    def _move_to_right(self, *args):
        ''' moves the widgets on the right smoothly '''
        self.div = self.num_transfers - 1

        if self.dest == (self.dest * self.page) / self.div:
            self.b_go_right.set_sensitive(False)

        if self.current > self.dest:
            self.current -= self.speed
            self.layout.move(self.hbox, self.current, 0)
            return True
        return False

    def _move_to_left(self, *args):
        ''' moves the widgets on the left smoothly '''
        if self.dest == 0: 
            self.b_go_left.set_sensitive(False)
        if self.dest >= 0:
            self.b_go_right.set_sensitive(True)
                
        if self.current < self.dest:
            self.current += self.speed
            self.layout.move(self.hbox, self.current, 0)
            return True
        return False

class FtWidget(gtk.HBox):
    '''this class represents the ui widget for one filetransfer'''
    def __init__(self, main_transfer_bar, transfer):
        gtk.HBox.__init__(self)

        self.main_transfer_bar = main_transfer_bar
        self.transfer = transfer
        
        self.event_box = gtk.EventBox()
        self.progress = gtk.ProgressBar()
        self.progress.set_ellipsize(pango.ELLIPSIZE_END)
        self.progress.add_events(gtk.gdk.BUTTON_PRESS_MASK)
        self.progress.connect('button-press-event', self._on_dbl_click_transfer)

        self.menu = gtk.Menu()

        img_file = gtk.image_new_from_stock(gtk.STOCK_FILE, \
                                        gtk.ICON_SIZE_BUTTON)
        img_dir = gtk.image_new_from_stock(gtk.STOCK_OPEN, \
                                        gtk.ICON_SIZE_BUTTON)

        m_open_file = gtk.ImageMenuItem(('Open file'))
        m_open_file.connect('activate', self._on_menu_file_clicked)
        m_open_file.set_image(img_file)

        m_open_dir = gtk.ImageMenuItem(('Open folder'))
        m_open_dir.connect('activate', self._on_menu_folder_clicked)
        m_open_dir.set_image(img_dir)

        self.menu.add(m_open_file)
        self.menu.add(m_open_dir)
        self.menu.show_all()

        self.event_box.add(self.progress)
        self.pack_start(self.event_box, False, False)
        self.pack_start(self.menu)

        self.buttons = []
        self.show_all()
        self.tooltip = FileTransferTooltip(self.event_box, self.transfer)

        self.event_box.connect('event', self._on_progressbar_event)

        self.do_update_progress()
        self.on_transfer_state_changed()

    def _on_dbl_click_transfer(self, widget, event):
        if event.button == 1 and event.type == gtk.gdk._2BUTTON_PRESS:
            if self.transfer.state == self.transfer.RECEIVED:
                self.transfer.open()

    def _on_progressbar_event(self, widget, event):
        if event.type == gtk.gdk.BUTTON_PRESS:
            if self.transfer.state == self.transfer.RECEIVED:
                if event.button == 3:
                    self.menu.popup(None, None, None, event.button, event.time)

    def _on_menu_file_clicked(self, widget):
        self.transfer.open()

    def _on_menu_folder_clicked(self, widget):
        self.transfer.opendir()
        
    def do_update_progress(self):
        ''' updates the progress bar status '''
        if self.transfer.state == self.transfer.RECEIVED:
            self.progress.set_fraction(1)  # 100%
        else:
            self.progress.set_fraction(self.transfer.getFraction())
        self.progress.set_text(self.transfer.getFilename())
        self.tooltip.update()

    def on_transfer_state_changed(self):
        ''' when the transfer changes its state '''
        state = self.transfer.state

        # remove existing buttons
        for button in self.buttons:
            self.remove(button)

        self.buttons = []

        if state == self.transfer.WAITING and self.transfer.sender != 'Me':
            button = gtk.Button(None, None)
            button.set_image(self.__get_button_img(gtk.STOCK_APPLY))
            button.connect('clicked', self._on_accept_clicked)
            self.buttons.append(button)

        if state in (self.transfer.RECEIVED, self.transfer.FAILED):
            button = gtk.Button(None, None)
            button.set_image(self.__get_button_img(gtk.STOCK_CLEAR))
            button.connect('clicked', self._on_close_clicked)
            self.buttons.append(button)

        if state == self.transfer.WAITING or state == self.transfer.TRANSFERING:
            b_cancel = gtk.Button(None, None)
            b_cancel.connect('clicked', self._on_cancel_clicked)
            b_cancel.set_image(self.__get_button_img(gtk.STOCK_CANCEL))
            self.buttons.append(b_cancel)

        for button in self.buttons:
            self.pack_start(button, False, False)

        self.show_all()
        self.do_update_progress()

    def __get_button_img(self, stock_img):
        ''' returns a gtk image '''
        img = gtk.Image()
        img.set_from_stock(stock_img, gtk.ICON_SIZE_MENU)
        return img

    def _on_cancel_clicked(self, widget):
        self.transfer.cancel()
        self.main_transfer_bar.hbox.remove(self)
        self.main_transfer_bar.num_transfers -= 1
        if self.main_transfer_bar.num_transfers == 0:
            self.main_transfer_bar.hide()

    def _on_accept_clicked(self, widget):
        self.transfer.accept()

    def _on_close_clicked(self, widget):
        self.transfer.remove()
        self.main_transfer_bar.hbox.remove(self)
        self.main_transfer_bar.num_transfers -= 1
        if self.main_transfer_bar.num_transfers == 0:
            self.main_transfer_bar.hide()

DELAY = 500

class FileTransferTooltip(gtk.Window):
    '''Class that implements the filetransfer tooltip'''
    def __init__(self, w_parent, transfer):
        gtk.Window.__init__(self, gtk.WINDOW_POPUP)

        self.transfer = transfer

        self.set_name('gtk-tooltips')
        self.set_position(gtk.WIN_POS_MOUSE)
        self.set_resizable(False)
        self.set_border_width(4)
        self.set_app_paintable(True)

        self.image = gtk.Image()
        self.details = gtk.Label()
        self.details.set_alignment(0, 0)

        self.table = gtk.Table(3, 2, False)
        self.table.set_col_spacings(5)

        self.add_label(('Status:'), 0, 1, 0, 1)
        self.add_label(('Average speed:'), 0, 1, 1, 2)
        self.add_label(('Time elapsed:'), 0, 1, 2, 3)
        self.add_label(('Estimated time left:'), 0, 1, 3, 4)

        self.status = gtk.Label()
        self.speed = gtk.Label()
        self.elapsed = gtk.Label()
        self.etl = gtk.Label()

        self.add_label('', 1, 2, 0, 1, self.status)
        self.add_label('', 1, 2, 1, 2, self.speed)
        self.add_label('', 1, 2, 2, 3, self.elapsed)
        self.add_label('', 1, 2, 3, 4, self.etl)

        vbox = gtk.VBox(False, 5)
        vbox.pack_start(self.details, False, False)
        vbox.pack_start(self.table, False, False)

        hbox = gtk.HBox(False, 5)
        hbox.pack_start(self.image, False, False)
        hbox.pack_start(vbox, True, True)

        self.add(hbox)

        self.connect('expose-event', self.on_expose_event)
        w_parent.connect('enter-notify-event', self.on_motion)
        w_parent.connect('leave-notify-event', self.on_leave)

        self.pointer_is_over_widget = False

    def add_label(self, l_string, left, right, top, bottom, label = None):
        ''' adds a label to the widget '''
        if label == None:
            label = gtk.Label(l_string)

        label.set_alignment(0, 0)
        self.table.attach(label, left, right, top, bottom)

    def on_motion(self, view, event):
        ''' called when the cursor is on the widget '''
        self.pointer_is_over_widget = True
        eventCoords = (event.x_root, event.y_root, int(event.y))
        gobject.timeout_add(DELAY, self.show_tooltip, \
                                            view, eventCoords)

    def show_tooltip(self, view, o_coords):
        ''' shows the tooltip with the transfer's informations '''
        # tooltip is shown after a delay, so we have to check
        # if mouse is still over parent widget
        if not self.pointer_is_over_widget:
            return

        pixbuf = self.transfer.getPreviewImage()

        #amsn sends a big. black preview? :S
        if pixbuf and pixbuf.get_height() <= 96 and pixbuf.get_width() <= 96:
            self.image.set_from_pixbuf(pixbuf)

        # set the location of the tooltip
        x, y = self.find_position(o_coords, view.window)
        self.move(x, y)
        self.update()
        self.show_all()
        return False

    def update(self):
        ''' updates the tooltip '''
        self.details.set_markup('<b>' + self.transfer.getFilename() + '</b>')
        time_left = self.transfer.getEstimatedTimeLeft()
        bps = self.transfer.getAverageSpeed()
        seconds = self.transfer.getElapsedTime()
        received, total = self.transfer.getBytes()

        percentage = int(self.transfer.getFraction() * 100)
        self.status.set_text('%d%% (%d/%d KB)' % (percentage, \
            int(received)/1024, int(total) / 1024))
        self.elapsed.set_text('%.2d:%.2d' % (int(seconds / 60), \
            int(seconds % 60)))
        self.speed.set_text('%.2f KiB/s' % (float(bps) / 1024.0))
        self.etl.set_text('%.2d:%.2d' % (int(time_left / 60), \
            int(time_left % 60)))

    def on_leave(self, view, event):
        ''' called when the pointer leaves the widget '''
        self.pointer_is_over_widget = False
        self.hide()

    # display a border around the tooltip
    def on_expose_event(self, tooltip_window, event):
        ''' called when the widget is going to be exposed '''
        width, height = tooltip_window.get_size()
        tooltip_window.style.paint_flat_box(tooltip_window.window, \
                                            gtk.STATE_NORMAL, gtk.SHADOW_OUT, \
                                            None, tooltip_window, 'tooltip', \
                                            0, 0, width, height)

    def find_position(self, o_coords, view_win):
        ''' finds the correct position '''
        x_root, y_root, origY = o_coords
        currentY = view_win.get_pointer()[1]

        width, height = self.get_size()
        s_width, s_height = gtk.gdk.screen_width(), gtk.gdk.screen_height()

        x = int(x_root) - width/2
        if currentY >= origY:
            y = int(y_root) + 24
        else:
            y = int(y_root) + 6

        # check if over the screen
        if x + width > s_width:
            x = s_width - width
        elif x < 0:
            x = 0

        if y + height > s_height:
            y = y - height - 24
        elif y < 0:
            y = 0

        return (x, y)
