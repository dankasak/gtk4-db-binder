import gi , sqlite3 , os

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk , Adw, GObject
from Gtk4DbBinder import Gtk4DbDatasheet, Gtk4DbForm
from states_window import States_Window

class Main_Window( object ):

    def __init__( self , globals ):

        self.globals = globals
        self.connection = globals['connection']
        self.builder = Gtk.Builder( self )
        self.builder.add_from_file( 'main_window.ui' )
        self.example_window = self.builder.get_object( 'main_window' )
        self.example_window.set_application( globals['application'] )

        self.css_provider = Gtk.CssProvider()

        self.customer_form = Gtk4DbForm.generator(
            connection = self.connection
            , sql = {
                "select": "*"
              , "from": "customers"
              , "where": "id=?"
              , "bind_values": [ 0 ]
            }
          , builder = self.builder
          , widget_prefix='customer.'
          , css_provider=self.css_provider
          , drop_downs = {
               "business_type_id": {
                   "sql": "select id , business_type from business_types"
                 , "bind_values": []
               }
           }
        )

        self.addresses = Gtk4DbDatasheet.generator(
            connection = self.connection
          , sql = {
                "select": "*"
              , "from": "addresses"
              , "where": "customer_id=?"
              , "bind_values": [ 0 ]
            }
          , fields = [
                {
                    'name': 'id'
                  # , 'type': 'text'
                  # , 'x_absolute': 120
                  , 'type': 'hidden'
                }
              , {
                    'name': 'customer_id'
                  , 'type': 'hidden'
                }
              , {
                    'name': 'address_line_1'
                  , 'type': 'text'
                  , 'x_percent': 25
                }
              , {
                    'name': 'address_line_2'
                  , 'type': 'text'
                  , 'x_percent': 25
                }
              , {
                    'name': 'city'
                  , 'type': 'text'
                  , 'x_percent': 20
                }
              , {
                    'name': 'state'
                  , 'type': 'drop_down'
                  , 'x_absolute': 120
                }
              , {
                    'name': 'country'
                  , 'type': 'text'
                  , 'x_percent': 20
                }
              , {
                    'name': 'postcode'
                  , 'type': 'text'
                  , 'x_percent': 10
                }
            ]
          , drop_downs = {
                'state': {
                    'sql': 'select id , state from states'
                  , 'bind_values': []
                }
            }
          , box = self.builder.get_object( 'addresses_box' )
        )

        self.customer_list = Gtk4DbDatasheet.generator(
            connection = self.connection
              , sql = {
                    "select": "id, name"
                  , "from": "customers"
                }
              , fields = [
                    {
                        'name': 'id'
                      , 'type': 'hidden'
                    }
                  , {
                        'name': 'name'
                      , 'type': 'text'
                      , 'x_percent': 100
                    }
               ]
          , box = self.builder.get_object( 'customer_list_box' )
          , no_auto_tools_box = True
        )

        self.customer_list.bind_to_child(
            self.customer_form
          , [
                {
                    'source': 'id'
                  , 'target': 'id'
                }
            ]
        )

        self.customer_list.bind_to_child(
            self.addresses
          , [
                {
                    'source': 'id'
                  , 'target': 'customer_id'
                }
            ]
        )

        self.example_window.present()

    def on_manage_states_clicked( self , button ):

        states = States_Window(
            self.globals
        )
