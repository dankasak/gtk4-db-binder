import gi , sqlite3 , os

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk , Adw, GObject
from Gtk4DbBinder import Gtk4DbDatasheet, Gtk4DbForm

from main_window import Main_Window

class ExampleApplication( Adw.Application ):

    def __init__( self , **kwargs ):
        super().__init__( **kwargs )
        self.connect( 'activate' , self.on_activate )

    def on_activate( self , app ):

        new_setup = not( os.path.isfile( 'example.db' ) )
        connection = sqlite3.connect( "example.db", isolation_level=None )
        if new_setup:
            cursor = connection.cursor()
            cursor.execute( """
                create table business_types (
                    id                   integer           primary key
                  , business_type        text not null
                );""" )
            customer_types = [
                ( 'Car Sales', )
              , ( 'Mining', )
              , ( 'Business Services', )
              , ( 'Religion', )
              , ( 'Media', )
            ]
            cursor.executemany(
                """insert into business_types ( business_type ) values ( ? )"""
              , customer_types )
            cursor.execute( """
                create table states (
                    id                   integer           primary key
                  , state                text not null
                );""" )
            states = [
                ( 'NSW', )
              , ( 'WA', )
              , ( 'CA', )
            ]
            cursor.executemany(
                """insert into states ( state ) values ( ? )"""
              , states
            )
            cursor.execute( """
                create table customers (
                    id                   integer           primary key
                  , name                 text not null
                  , contract_start_date  date not null
                  , contract_end_date    date
                  , business_type_id     integer
                );""" )
            customers = [
                ( 'Dodgy Bros Car Sales', '2020-07-01', None , 1 )
              , ( 'Hancock Prospecting', '2022-01-12', None , 2 )
              , ( 'Trust Us Data Broker', '2003-04-01', '2013-02-14' , 3 )
              , ( 'Followers of the Only True God inc', '2018-12-25', None , 4 )
              , ( 'Faux Media', '1989-12-13', None , 5 )
            ]
            cursor.executemany(
                """insert into customers ( name , contract_start_date , contract_end_date , business_type_id )
                       values ( ? , ? , ? , ? )"""
                , customers )
            cursor.execute( """
                create table addresses (
                    id                  integer           primary key
                  , customer_id         int    not null
                  , address_line_1      text
                  , address_line_2      text
                  , city                text
                  , state               int
                  , country             text
                  , postcode            text
                );""" )
            addresses = [
                ( 1 , 'Parramatta Road' , None , 'Granville' , 1 , 'Australia' , 2142 )
              , ( 1 , 'Parramatta Road' , None , 'Auburn' , 1 , 'Australia' , None )
              , ( 2 , 'HPPL House', '28-42 Ventnor Avenue' , 'West Perth' , 2 , 'Australia' , 6005 )
              , ( 3 , 'P.O.Box 549' , 'KY1-1602, Corner of Mary Street and Sheddon Road' , 'Grand Cayman' , 3 , 'Cayman Islands' , 'KY1-1602' )
              , ( 4 , 'Hillsong Convention Centre' , '1 Solent Cct' , 'Norwest' , 1 , 'Australia' , 2153 )
              , ( 5 , '2 Holt Street' , None , 'Surry Hills' , 1 , 'Australia' , 2010 )
            ]
            for i in range( 0, 200 ):
                cursor.executemany(
                    """insert into addresses ( customer_id, address_line_1 , address_line_2 , city, state,country, postcode )
                           values ( ? , ? , ? , ? , ? , ? , ? )"""
                  , addresses )
            connection.commit()

        globals = {
            'application': self
          , 'connection': connection
        }

        main_window = Main_Window( globals )

app = ExampleApplication()

app.run()
