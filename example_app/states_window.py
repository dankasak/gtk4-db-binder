import gi , sqlite3 , os

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk , Adw, GObject
from Gtk4DbBinder import Gtk4DbDatasheet, Gtk4DbForm

class States_Window( object ):

    def __init__( self , globals ):

        self.globals = globals
        self.connection = globals['connection']
        self.builder = Gtk.Builder( self )
        self.builder.add_from_file( 'states_window.ui' )
        self.states_window = self.builder.get_object( 'states_window' )
        self.states_window.set_application( globals['application'] )

        self.css_provider = Gtk.CssProvider()

        self.states_datasheet = Gtk4DbDatasheet.generator(
            connection = self.connection
            , sql = {
                "select": "*"
              , "from": "states"
            }
          , box = self.builder.get_object( 'states_datasheet_box' )
        )

        self.states_window.present()
