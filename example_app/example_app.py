import gi , sqlite3 , os

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk , Adw
from Gtk4DbBinder import Gtk4DbDatasheet, Gtk4DbForm

class ExampleApplication( Adw.Application ):

    def __init__( self , **kwargs ):
        super().__init__( **kwargs )
        self.connect( 'activate' , self.on_activate )

    def on_activate( self , app ):

        self.builder = Gtk.Builder( self )
        self.builder.add_from_file( 'example_app.ui' )
        self.example_window = self.builder.get_object('main_window')
        self.example_window.set_application( self )

        self.connection = self.connect_and_init_sqlite()

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
        )

        self.addresses = Gtk4DbDatasheet.generator(
            connection = self.connection
            , sql = {
                # "select": "id, customer_id, address_line_1, address_line_2, city, country, postcode"
                "select": "*"
              , "from": "addresses"
              , "where": "customer_id=?"
              , "bind_values": [ 0 ]
            }
            # , fields = [
            #     {
            #         'name': 'id'
            #       , 'type': 'hidden'
            #     }
            #   , {
            #         'name': 'customer_id'
            #       , 'type': 'hidden'
            #     }
            #   , {
            #         'name': 'address_line_1'
            #       , 'type': 'text'
            #       , 'x_percent': 25
            #     }
            #   , {
            #         'name': 'address_line_2'
            #       , 'type': 'text'
            #       , 'x_percent': 25
            #     }
            #   , {
            #         'name': 'city'
            #       , 'type': 'text'
            #       , 'x_percent': 20
            #     }
            #   , {
            #         'name': 'country'
            #       , 'type': 'text'
            #       , 'x_percent': 20
            #     }
            #   , {
            #         'name': 'postcode'
            #       , 'type': 'text'
            #       , 'x_percent': 10
            #     }
            # ]
          , box = self.builder.get_object( 'addresses_box' )
          , before_insert = self.before_addresses_insert
          , on_insert = self.on_addresses_insert
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
          , on_row_select = self.on_customer_row_select
          , no_auto_tools_box = True
        )

        self.example_window.present()

    def on_customer_row_select( self , grid_row ):

        self.customer_form.query( bind_values = [ grid_row.id ] )
        self.addresses.query( bind_values = [ grid_row.id ] )

    def connect_and_init_sqlite( self ):

        new_setup = not( os.path.isfile( 'example.db' ))
        connection = sqlite3.connect( "example.db", autocommit=True )
        if new_setup:
            cursor = connection.cursor()
            cursor.execute( """
                create table customers (
                    id                   integer           primary key
                  , name                 text not null
                  , contract_start_date  date not null
                  , contract_end_date    date
                );""" )
            customers = [
                ( 'Dodgy Bros Car Sales', '2020-07-01', None )
              , ( 'Hancock Prospecting', '2022-01-12', None )
              , ( 'Trust Us Data Broker', '2003-04-01', '2013-02-14' )
              , ( 'Followers of the Only True God inc', '2018-12-25', None )
              , ( 'Faux Media', '1989-12-13', None )
            ]
            cursor.executemany(
                """insert into customers ( name , contract_start_date , contract_end_date )
                       values ( ? , ? , ? )"""
                , customers )
            cursor.execute( """
                create table addresses (
                    id                  integer           primary key
                  , customer_id         int    not null
                  , address_line_1      text
                  , address_line_2      text
                  , city                text
                  , country             text
                  , postcode            int
                );""" )
            addresses = [
                ( 1, 'Parramatta Road' , None , 'Granville', 'Australia', 2142 )
              , ( 1, 'Parramatta Road' , None , 'Auburn', 'Australia', None )
              , ( 2, 'HPPL House', '28-42 Ventnor Avenue', 'West Perth', 'Australia', 6005 )
            ]
            for i in range( 0, 1000 ):
                cursor.executemany(
                    """insert into addresses ( customer_id, address_line_1 , address_line_2 , city, country, postcode )
                           values ( ? , ? , ? , ? , ? , ? )"""
                  , addresses )
            connection.commit()
        return connection

    def before_addresses_insert( self ):

        customer_id = self.customer_list.get_column_value( "id" )
        if customer_id is not None:
            return True
        else:
            return False

    def on_addresses_insert( self ):

        customer_id = self.customer_list.get_column_value( "id" )
        self.addresses.set_column_value( "customer_id" , customer_id )

    def on_apply( self , something ):
        self.form.apply()

app = ExampleApplication()

app.run()
