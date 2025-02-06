#!/usr/bin/env python3
"""
Name: Gtk4DbBiner

Description: Creates a liststore interface to a database table
             and binds it to a datasheet or form.

             For the datasheet version, you pass a box which
             gets populated with a ScrolledWindow and ColumnView.

             For the form version, you pass a Gtk Builder UI definition,
             which you can generate using Cambalache ( a WYSIWYG editor ).
             Widgets with names matching column names will be bound.

Usage

License

# todo add module level docstrings
"""

import pathlib
import gi
gi.require_version( "Gtk" , "4.0" )
from gi.repository import Gtk, Gio, Gdk, Pango, GObject, GLib
import json , uuid , importlib.util , sys , re , time

# Define some 'constants'
# These are the names of icons we render for the relevant record statuses
UNCHANGED = "emblem-default"
CHANGED   = "media-playlist-shuffle"
INSERTED  = "list-add"
DELETED   = "list-remove"
LOCKED    = "security-high"

class GridWidget( Gtk.Widget ):

    def __init__( self , column_name="oops" , **kwargs ):

        super().__init__( **kwargs )
        self.model_position = -1
        self.column_name = column_name


class GridEntry( Gtk.Entry , GridWidget ):

    def __init__( self , **kwargs ):

        super().__init__( **kwargs )


class GridDropDown( Gtk.DropDown , GridWidget ):

    def __init__( self , **kwargs ):

        super().__init__( **kwargs )


class GridLabel( Gtk.Label , GridWidget ):

    def __init__( self , **kwargs ):

        super().__init__( **kwargs )


class GridImage( Gtk.Image , GridWidget ):

    def __init__( self , **kwargs ):

        super().__init__( **kwargs )


class ForeignKeyBinder( GObject.Object ):
    __gtype_name__ = 'ForeignKeyBinder'

    def __init__( self , keys_list , mapping , parent_friendly_table_name ):

        super().__init__()
        self._keys_list = keys_list
        self._keys_dict_json = '{}'
        self.mapping = mapping
        self.parent_friendly_table_name = parent_friendly_table_name
        for key in keys_list:
            setattr( self , key , None )

    @GObject.Property( type=str )
    def keys_dict_json( self ):
        return self._keys_dict_json

    @keys_dict_json.setter
    def keys_dict_json( self , keys_dict_json ):
        if self._keys_dict_json != keys_dict_json:
            self._keys_dict_json = keys_dict_json
            self.notify( "keys_dict_json" )


class KeyValueModel ( GObject.Object ):
    __gtype_name__ = 'KeyValueModel'

    """A generic key/value model, useful for DropDown widgets"""

    def __init__( self , key , value ):
        super().__init__()

        self._key = key
        self._value = value

    @GObject.Property
    def key( self ):
        return self._key

    @GObject.Property
    def value( self ):
        return self._value


class Gtk4DbAbstract( object ):

    """This logic is common to Form and Datasheet classes"""

    def setup_fields( self , rebuild=False  ):

        if rebuild:
            self.fields = {}
        elif self.fields_setup:
            return True

        """
           If there are no field definitions, then create some from our fieldlist from the database
           TODO: fix no_autosizing
        """

        #    if ( not $self->{fields} and not exists $self->{no_autosizing} ) {
        if not self.fields:
            no_of_fields = len( self.fieldlist )
            if no_of_fields:
                if no_of_fields < 15:
                    for field in self.fieldlist:
                        self.fields.append(
                            {
                                "name"      : field
                              , "x_percent" : 100 / no_of_fields
                            }
                        )
                else:
                    # Don't set percentages < 12.5 - doesn't really work so well ...
                    for field in self.fieldlist:
                        self.fields.append(
                            {
                                "name"       : field
                              , "x_absolute" : 100
                            }
                        )

        if not self.primary_keys:
            self.read_only = True
            if not self.quiet:
                print( "\nCouldn't fetch a primary key for {0}".format( self.friendly_table_name ) + "\n" \
                       " ... This will happen in a multi-table query ...\n" \
                       " ... Defaulting to read-only ...\n\n" )

        # Fill in renderer types
        column_no = 0
        for field in self.fields:
            # Set up column name <==> column number mapping
            self.column_name_to_number_mapping[ field['name'] ] = column_no
            # Grab a default renderer type if one hasn't been defined
            if 'type' not in field.keys():
                sql_name = self.column_name_to_sql_name( field['name'] )
                fieldtype = self.column_info[ sql_name ]['type']
                if not fieldtype:
                    field['type'] = "text"
                elif re.search( r'INT|DOUBLE' , fieldtype , re.IGNORECASE ):
                    field['type'] = "number"
                    # Setting up a number hash forces numeric sorting
                    if "number" not in field.keys():
                        field['number'] = {}
                elif re.search( r'CHAR' , fieldtype , re.IGNORECASE ):
                    field['type'] = "text"
                elif re.search( r'TIMESTAMP' , fieldtype , re.IGNORECASE ):
                    field['type'] = "timestamp"
                elif re.search( r'DATE' , fieldtype , re.IGNORECASE ):
                    field['type'] = "date"
                elif fieldtype == "TIME":
                    field['type'] = "time"
                else:
                    field['type'] = "text"

            if field['type'] == "none":
                field['type'] = "hidden"

            field['column'] = column_no
            column_no = column_no + 1
        self.fields_setup = True

        return True

    def dialog( self , title="Gtk4 DB Binder dialog" , type="info" , text=None , markup = None , handler=None ):

        if not text and not markup:
            raise Exception( "dialog wasn't passed text or markup!" )

        headerbar = Gtk.HeaderBar( show_title_buttons = False )
        modal = Gtk.Window( modal = True , title = title )
        modal.set_transient_for( self.window )
        modal.set_titlebar( headerbar )
        vbox = Gtk.Box( orientation = Gtk.Orientation.VERTICAL , spacing = 10
                        , margin_top = 10 , margin_bottom = 10 , margin_start = 10 , margin_end = 10 )
        button_box = Gtk.Box( orientation = Gtk.Orientation.HORIZONTAL , spacing = 10 )
        label = Gtk.Label ()
        if text:
            label.set_text( text )
        else:
            label.set_markup( markup )

        if type == "info":
            button_box.append( self.icon_button( label_text='OK' , markup="" , icon_name='gtk-info' , handler=lambda x: self.dialog_handler( modal , handler , 'OK' ) ) )
        elif type == "question":
            button_box.append( self.icon_button( label_text='Yes' , markup="" , icon_name='gtk-yes' , handler=lambda x: self.dialog_handler( modal , handler, True ) ) )
            button_box.append( self.icon_button( label_text='No' , markup="" , icon_name='gtk-no' , handler=lambda x: self.dialog_handler( modal , handler,  False ) ) )
        elif type == "warning" or type == "error":
            button_box.append( self.icon_button( label_text='Doh' , markup="" , icon_name='gtk-info' , handler=lambda x: self.dialog_handler( modal , handler,  'OK' ) ) )

        vbox.append( label )
        vbox.append( button_box )
        modal.set_child( vbox )
        modal.show()

    def dialog_handler( self , modal , handler , response ):

        modal.destroy()
        if handler:
            handler( response )

    def on_toplevel_closed( self , something ):

        if self.any_changes():
            if self.auto_apply:
                if not self.apply():
                    return False # Apply method will already give a dialog explaining error
            else:
                if len( self.custom_changed_text ):
                    dialog_text = self.custom_changed_text
                else:
                    dialog_text = "There are outstanding changes to the currently bound table ( {0} ).\n" \
                                  " Do you want to apply them before closing the window?".format( self.friendly_table_name )
                self.dialog(
                    title   = "Apply changes to {0} before querying?".format( self.friendly_table_name )
                  , type    = "question"
                  , text    = dialog_text
                  , handler = self.close_window_outstanding_changes_dialog_handler
                )
            return True # We need to return True here, or the window will be closed

    def query_outstanding_changes_dialog_handler( self , response ):

        # The user has been asked if they want to apply changes before re-querying
        if response:
            self.apply()
        self._do_query()

    def close_window_outstanding_changes_dialog_handler ( self , response ):

        # The user has been asked if they want to apply changes before closing the window
        if response:
            self.apply()
        self.window.destroy()

    def query( self , where=None , bind_values=None , dont_apply=False ):

        if where:
            self.sql['where'] = where
        if bind_values:
            self.sql['bind_values'] = bind_values

        # Handle outstanding changes in the current datasheet, if it exists
        if self.widget_setup:
            if not dont_apply and not self.read_only:
                if self.any_changes():
                    if self.auto_apply:
                        if not self.apply():
                            return False # Apply method will already give a dialog explaining error
                    else:
                        if len( self.custom_changed_text ):
                            dialog_text = self.custom_changed_text
                        else:
                            dialog_text = "There are outstanding changes to the currently bound table ( {0} ).\n" \
                                          " Do you want to apply them before running a new query?".format( self.friendly_table_name )
                        self.dialog(
                            title   = "Apply changes to {0} before querying?".format( self.friendly_table_name )
                          , type    = "question"
                          , text    = dialog_text
                          , handler = self.query_outstanding_changes_dialog_handler
                        )
                        return True # Maybe we should think more about this

        self._do_query()

        return True

    def _do_query( self ):

        """Generates and executes a query to fetch data.
        Fetches primary keys and column info
        Returns a cursor ( not yet fetched from )"""

        if hasattr( self , 'before_query' ):
            self.before_query()

        # Fetch primary key(s), but only if we dont have some ( they can be passed in the constructor,
        # or we could have some from a previous query() call )

        if not hasattr( self , 'primary_keys' ):
            if self.read_only or 'pass_through' in self.sql.keys():
                self.primary_keys = []
            else:
                self.primary_keys = self.primary_key_info( None , None , self.sql['from'] )

        sql = ""
        if 'pass_through' in self.sql.keys():
            sql = self.sql['pass_through']
        else:
            sql = "select {0}".format( self.sql['select'] )
            if self.sql['select'] != "*":
                sql_fields = [ x.strip() for x in self.sql['select'].split( ',' ) ]
                for primary_key_item in self.primary_keys:
                    if primary_key_item not in sql_fields:
                        sql = sql + ", {0}".format( primary_key_item )
            sql = sql + " from {0}".format( self.sql['from'] )
            if 'where' in self.sql.keys():
                sql = sql + " where {0}".format( self.sql['where'] )
            if 'order_by' in self.sql.keys():
                sql = sql + " order by {0}".format( self.sql['order_by'] )
            if 'limit' in self.sql.keys():
                sql = sql + " limit {0}".format( self.sql['limit'] )
        if 'bind_values' not in self.sql.keys():
            self.sql['bind_values'] = []

        try:
            cursor = self.connection.cursor()
            self.execute( cursor , sql , self.sql['bind_values'] )
        except Exception as e:
            print( "Oh nos! {0}".format( e ) )
            if self.dump_on_error:
                print ( "SQL was:\n{0}".format( sql ) )
            return False

        self.fieldlist = self.column_names_from_cursor( cursor )
        self.column_info = self.fetch_column_info( cursor )

        self.new_where_dict = {}

        return cursor

    def insert( self , button , row_state = INSERTED , columns_and_values = {} , *args ):

        if self.before_insert:
            if not self.before_insert():
                return False

        foreign_keys = {}
        if self.foreign_key_binder:
            foreign_keys = json.loads( self.foreign_key_binder.keys_dict_json )
            if not foreign_keys:
                self.dialog(
                    title  = "Can't insert yet!"
                  , type   = "error"
                  , markup = "This object is bound to a parent [ {0} ], but the parent is not populated, so there are no foreign keys".format( self.foreign_key_binder.parent_friendly_table_name )
                )
                return False

        new_record_values = []
        for i in self.fieldlist:
            this_value = None
            if i in columns_and_values.keys():
                this_value = columns_and_values[ i ]
            if i in foreign_keys.keys():
                this_value = foreign_keys[ i ]
            new_record_values.append( this_value )

        new_grid_row = self.grid_row_class( 0 , new_record_values )
        new_grid_row.row_state = row_state
        self.model.append( new_grid_row )

        if self.on_insert:
            self.on_insert()

        return True

    def undo( self , *args ):

        self.query( dont_apply=True )
        return True

    def _do_delete( self , row=None ):

        primary_key_filter_components = []
        values = []
        sql = "delete from {0} where ".format( self.sql['from'] )
        for primary_key_item in self.primary_keys:
            column_no = self.column_from_sql_name( primary_key_item )
            primary_key_filter_components.append( self._db_prepare_update_column_fragment( self.fields[ column_no ] , primary_key_item ) )
            values.append( getattr( row , primary_key_item ) )
        sql = sql + " and ".join( primary_key_filter_components )

        try:
            cursor = self.connection.cursor()
            self.execute( cursor , sql , values )
        except Exception as e:
            self.dialog(
                title="Error deleting record!"
              , type="error"
              , markup="<b>Database server says:</b>\n\n{0}}".format( e )
            )
            if self.dump_on_error:
                print ( "SQL was:\n{0}".format( sql ) )
            return False

        return True

    def column_from_sql_name( self , sql_fieldname ):

        # Take an *SQL* field name and return the column that the field is in
        counter = 0
        for field in self.fieldlist:
            if field.upper() == sql_fieldname.upper():
                return counter
            counter = counter + 1

    def column_from_column_name( self, column_name ):

        # Take a *COLUMN* name and returns the column that the field is in
        if column_name in self.column_name_to_number_mapping.keys():
            return self.column_name_to_number_mapping[ column_name ]
        else:
            print( "column_from_column_name() called with an unknown column name! ( {0} )".format( column_name ) )
            return -1

    def column_name_to_sql_name( self , column_name ):

        # This function converts a column name to an SQL field name
        column_no = self.column_from_column_name( column_name )
        return self.fieldlist[ column_no ]

    def _db_prepare_update_column_fragment( self , column_definition , column_name ):

        # Prepare a "column_name = %s" string for update statements.
        # Sub-classes can do things like apply formatting or functions, eg Oracle
        # has to call to_date() for values going into date columns

        return "{0} = %s".format( column_name )

    def _db_prepare_insert_column_fragment( self , column_definition , column_name ):

        # Prepare a placeholder string for insert statements ( usually just a: %s )
        # Sub-classes can do things like apply formatting or functions, eg Oracle
        # has to call to_date() for values going into date columns

        return "%s"

    def _do_insert( self , row=None ):

        sql_fields_list = []
        values = []
        placeholders_list = []

        for column_name in self.fieldlist:
            if column_name in self.primary_keys:
                if self.auto_incrementing:
                    continue
            column_no = self.column_from_sql_name( column_name )
            placeholders_list.append( self._db_prepare_insert_column_fragment( self.fields[ column_no ] , column_name ) )
            sql_fields_list.append( column_name )
            value = getattr( row , column_name )
            if 'number' in self.fields[ column_no ].keys():
                value = re.sub( "[^\d\.]", "" , value )
            values.append( value )

        sql = "insert into {0} ( {1} ) values ( {2} )".format(
            self.sql['from']
            , " , ".join( sql_fields_list )
            , " , ".join( placeholders_list )
        )

        try:
            cursor = self.connection.cursor()
            self.execute( cursor , sql , values )
        except Exception as e:
            self.dialog(
                title="Error inserting record!"
              , type="error"
              , markup="<b>Database server says:</b>\n\n{0}".format( e )
            )
            if self.dump_on_error:
                print ( "SQL was:\n{0}".format( sql ) )
            return False

        # If we just inserted a record, we have to fetch the primary key and replace the current '!' with it
        if self.auto_incrementing:
            for key_name in self.primary_keys:
                setattr( row , key_name , self.last_insert_id( cursor ) )

        self._set_record_unchanged( row=row )

        return True

    def _set_record_unchanged( self , row=None ):

        if self.data_lock_field:
            if getattr( row , self.column_from_sql_name( self.data_lock_field ) ):
                row.row_state = LOCKED
            else:
                row.row_state = UNCHANGED
        else:
            row.row_state = UNCHANGED

    def _do_update( self , row=None ):

        sql_fields_list = []
        values = []

        for column_name in self.fieldlist:
            # SQL Server, amongst others, doesn't allow updates of primary keys
            column_no = self.column_from_sql_name( column_name )
            if (    column_name in self.primary_keys
                    and self.dont_update_keys
            ) or ( 'dont_update' in self.fields[ column_no ] ) \
                    or column_name == "" \
                    or 'sql_ignore' in self.fields[ column_no ]:
                continue
            sql_fields_list.append( self._db_prepare_update_column_fragment( self.fields[ column_no ] , column_name ) )
            value = getattr( row , column_name )
            if 'number' in self.fields[ column_no ].keys():
                value = re.sub( "[^\d\.]", "" , value )
            values.append( value )

        sql = "update {0} set {1} where ".format(
            self.sql['from']
            , " , ".join( sql_fields_list )
        )

        placeholder_list = []
        for primary_key_item in self.primary_keys:
            column_no = self.column_from_sql_name( primary_key_item )
            placeholder_list.append( self._db_prepare_update_column_fragment( self.fields[ column_no ] , primary_key_item ) )
#            values.append( getattr( row , primary_key_item ) )
            # For databases that support updating the primary key, we need to use the *original* value in the filter
            values.append( row.get_original_value( primary_key_item ) )
        sql = sql + " and ".join( placeholder_list )

        try:
            cursor = self.connection.cursor()
            self.execute( cursor , sql , values )
        except Exception as e:
            print( "{0}".format( e ) )
            self.dialog(
                title="Error updating record!"
              , type="error"
              , markup="<b>Database server says:</b>\n\n{0}\n\nSQL:\n{1}\n\nValues:\n{2}".format( e , sql , values )
            )
            if self.dump_on_error:
                print ( "SQL was:\n{0}".format( sql ) )
            return False

        self._set_record_unchanged( row=row )

        return True

    def icon_button( self , label_text="" , markup="" , icon_name='gtk-ok' , handler=None ):

        button = Gtk.Button()
        label  = Gtk.Label()
        if len( markup ):
            label.set_markup( markup )
        else:
            label.set_text( label_text )
        icon = Gtk.Image.new_from_icon_name( icon_name )
        icon.set_hexpand( True )
        box = Gtk.Box( orientation = Gtk.Orientation.HORIZONTAL , spacing = 5 )
        label.set_xalign( 0 )
        label.set_hexpand( True )
        icon.set_halign( Gtk.Align.END )
        box.append( icon )
        box.append( label )
        button.set_child( box )
        if handler:
            button.connect( 'clicked', handler )
        else:
            button.connect( 'clicked', getattr( self , label_text ) )
        return button

    def setup_recordset_tools( self ):

        for item_name in self.recordset_items:
            if item_name in self.supported_recordset_items:
                this_item = self.supported_recordset_items[ item_name ]
            elif item_name in self.recordset_extra_tools:
                this_item = self.recordset_extra_tools[ item_name ]
            else:
                raise Exception( "Unsupported recordset tool item: {0}".format( item_name ) )

            if this_item['type'] == 'button':
                handler = None
                markup = ''
                if 'handler' in this_item.keys():
                    handler = this_item['handler']
                if 'markup' in this_item.keys():
                    markup = this_item['markup']
                widget = self.icon_button(
                    label_text = item_name
                  , icon_name  = this_item['icon_name']
                  , handler    = handler
                  , markup     = markup
                )
            elif this_item['type'] == 'spinbutton':
                adjustment = Gtk.Adjustment.new( 1 , 1 , 200 , 1 , 10, 0 )
                widget = Gtk.SpinButton.new( adjustment , 1 , 0 )
                widget.connect( 'value-changed' , self.handle_spinner_update )
                self.spinner = widget

            self.recordset_tools_box.append( widget )

    def handle_spinner_update( self , widget ):

        self.move( None , int( widget.get_value() - 1 ) ) # Spinner starts at 1. Model starts at 0.

    def set_spinner_range( self ):

        if self.spinner:
            adjustment = self.spinner.get_adjustment()
            record_count = len( self.model )
            adjustment.set_upper( record_count )

    def data_to_csv( self , button ):

        raise Exception( "Not implemented! ")

    def execute( self , cursor , sql , params={} ):

        start_time = time.time()

        try:
            if len( params ) == 0:
                cursor.execute( sql )
            else:
                cursor.execute( sql , params )
        except Exception as e:
            raise e

        end_time = time.time()
        print( "DB execute() completed in {0} seconds".format( round( end_time - start_time ) , 2 ) )

    def fetchrow_dict( self , cursor ):

        cursor_id = id( cursor )

        if cursor_id not in self.cursor_ids.keys():
            self.cursor_ids[ cursor_id ] = self.column_names_from_cursor( cursor )

        column_names = self.cursor_ids[ cursor_id ]

        for record in cursor:
            record_dict = dict( zip( column_names , record ) )
            yield record_dict

    def fetch_column_info( self , cursor ):

        column_info = {}
        return column_info

    def column_names_from_cursor( self , cursor ):
        raise Exception( "The column_names_from_cursor() method needs to be implemented by a subclass" )

    def generate_grid_row_class ( self , column_definitions ):

        """This method generates a GridRow class, based on the columns in the query.
        We need to do this, as the bindings use decorators, and there doesn't appear to be a way
        to dynamically configure decorators"""

        unique_class_name = "GridRow_" + uuid.uuid4().hex[:6].upper()

        class_def = "from gi.repository import Gtk, Gio, Gdk, Pango, GObject, GLib\n\n" \
                    "class " + unique_class_name + "( GObject.Object ):\n    __gtype_name__ = '" + unique_class_name + \
                    "'\n\n" \
                    "    def __init__( self , track , record ):\n" \
                    "\n" \
                    "        super().__init__()\n" \
                    "        self._track = track\n" \
                    "        self._row_state = '{0}'\n".format( UNCHANGED )

        class_def = class_def + "        self._original_values_dict = {} # mainly useful for DBs that allow updates to primary keys\n" \
                    "\n" \
                    "        # Unpack record into class attributes ... and convert NULL / None to ''\n"

        access_methods = [
            "    @GObject.Property(type=str)\n" \
            "    def row_state( self ):\n" \
            "        return self._row_state\n" \
            "\n" \
            "    @row_state.setter\n" \
            "    def row_state( self , row_state ):\n" \
            "        if self._row_state != row_state:\n" \
            "            self._row_state = row_state\n" \
            "            self.notify( \"row_state\" )\n    "
        ]

        indirect_p1 = "{0}"
        indirect_p2 = "{1}"

        for i in range( 0 , len( column_definitions ) ):
            # class_def = class_def + "        if record[ {0} ] is not None:\n".format( i )
            # class_def = class_def + "            self._{0} = record[ {1} ]\n".format( column_definitions[ i ]['name'] , i )
            # class_def = class_def + "        else:\n"
            # class_def = class_def + "            self._{0} = ''\n".format( column_definitions[ i ]['name'] )
            # class_def = class_def + "#        print( \"{0} attr set to: {1}\".format( self._{0} ) )\n\n".format( column_definitions[ i ]['name'] , indirect_p1 )

            class_def = class_def + "        self._{0} = record[ {1} ]\n".format( column_definitions[ i ]['name'] , i )

            access_methods.append (
                "    @GObject.Property(type=str)\n" \
                "    def {0}( self ):\n" \
                "        return self._{0}\n" \
                "\n" \
                "    @{0}.setter\n" \
                "    def {0}( self , {0} ):\n" \
                "#        print( \"In [{0}].setter() ... current: [{3}] ... new: [{4}]\".format( {0} , self._{0} ) )\n" \
                "        if str( self._{0} ) != {0}:\n" \
                "#            print( \"[{0}] changed\" )\n"
                "            self.notify( \"{0}\" )\n" \
                "            if self.row_state == '{1}':\n" \
                "                self.set_original_value( '{0}' , self._{0} )\n" \
                "#                print( \"grid row state ==> changed\" )\n" \
                "                self.row_state = '{2}'\n" \
                "                self.notify( \"row_state\" )\n" \
                "            self._{0} = {0}\n" \
                "    ".format(
                    column_definitions[ i ]['name'] # 0
                    , UNCHANGED # 1
                    , CHANGED # 2
                    , indirect_p1 # 3 ==> {0}
                    , indirect_p2 # 4 ==> {1}
                ) )

        class_def = class_def + "\n" + "\n".join( access_methods )

        class_def = class_def + "\n    def track( self ):\n" \
            "        return self._track\n" \
            "\n" \
            "    def set_original_value( self , column , value ):\n" \
            "        self._original_values_dict[ column ] = value\n" \
            "\n" \
            "    def get_original_value( self , column ):\n" \
            "        if column in self._original_values_dict.keys():\n" \
            "            return self._original_values_dict[ column ]\n" \
            "        else:\n" \
            "            return getattr( self , column )\n"

        # print( "Class definition:\n{0}".format( class_def ) )
        tmp_class_path = "/tmp/{0}.py".format( unique_class_name )

        with open( tmp_class_path , "w" ) as class_file:
            class_file.write( class_def )

        # https://stackoverflow.com/questions/67631/how-can-i-import-a-module-dynamically-given-the-full-path
        spec = importlib.util.spec_from_file_location( unique_class_name , tmp_class_path )
        module = importlib.util.module_from_spec( spec )
        sys.modules[ unique_class_name ] = module
        spec.loader.exec_module( module )
        self.grid_row_class = getattr( module , unique_class_name )

        return self.grid_row_class

    def generate_model( self , column_definitions , data ):

        grid_row_class = self.generate_grid_row_class( column_definitions )
        model = Gio.ListStore.new( grid_row_class )
        track = 0

        for row in data:
            model.append( grid_row_class( track , row ) )
            track = track + 1

        self.grid_row_class = grid_row_class
        self.model = model

        return model

    def bind_to_child( self , child_gtk4_db_binder , column_mapping_list ):

        """
           Bind to a child form/datasheet object, so that when:
               - a new record is navigated to
               - a new value is entered any column in column_list
              ... we can automate the process of requerying ( which is otherwise tedious )
              ... and also handle inserts in the child object
        """

        child_keys_list = []
        for column_mapping in column_mapping_list:
            """
               Each column_mapping is a dict with a 'source' and 'target' column.
               We create a ForeignKeyBinder in the child, and the child will in turn connect to the FKB's notify signal
               to trigger actions that need to occur when we push changes to the object.
            """
            child_keys_list.append( column_mapping['target'] )

        this_foreign_key_binder = child_gtk4_db_binder.create_foreign_key_binder( child_keys_list , column_mapping_list , self.friendly_table_name )
        self.child_foreign_key_binders.append( this_foreign_key_binder )

        if len( self.datasheet.model ):
            self.sync_grid_row_to_foreign_key_binding( self.get_current_grid_row() , this_foreign_key_binder )
        else:
            self.sync_grid_row_to_foreign_key_binding( None , this_foreign_key_binder )

    def create_foreign_key_binder( self , keys_list , mapping , parent_friendly_table_name ):

        self.foreign_key_binder = ForeignKeyBinder( keys_list , mapping , parent_friendly_table_name )
        self.foreign_key_binder.connect( 'notify' , self.handle_parent_foreign_key_update )
        return self.foreign_key_binder

    def handle_parent_foreign_key_update( self , foreign_key_binder , g_param_spec ):

        """Here we handle a parent binder being updated"""

        keys_dict = json.loads( foreign_key_binder.keys_dict_json )
        filter_list = []
        key_values_list = []
        for key in keys_dict:
            filter_list.append( self._db_prepare_update_column_fragment( self.fields[ self.column_name_to_number_mapping[ key ] ] , key ) )
            key_values_list.append( keys_dict[ key ] )
        filter_string = " and ".join( filter_list )

        self.query(
            where = filter_string
          , bind_values = key_values_list
        )

    def setup_drop_down_factory_and_model( self , sql , bind_values ):

        cursor = self.connection.cursor()
        cursor.execute( sql , bind_values )
        model = Gio.ListStore( item_type = KeyValueModel )
        for record in cursor:
            model.append( KeyValueModel( record[0] , record[1] ) )

        # Set up the factory
        factory = Gtk.SignalListItemFactory()
        factory.connect( "setup", self.on_drop_down_factory_setup )
        factory.connect( "bind", self.on_drop_down_factory_bind )

        return factory , model

    def on_drop_down_factory_setup( self , factory , list_item ):

        # Set up the child of the list item; this can be an arbitrarily
        # complex widget but we use a simple label now
        label = Gtk.Label()
        list_item.set_child( label )

    def on_drop_down_factory_bind( self , factory , list_item ):

        # Bind the item in the model to the row widget; again, since
        # the object in the model can contain multiple properties, and
        # the list item can contain any arbitrarily complex widget, we
        # can have very complex rows instead of the simple cell renderer
        # layouts in GtkComboBox
        label = list_item.get_child()
        key_value_object = list_item.get_item()
        label.set_text( key_value_object.value )

    def bind_dropdown_transform_to( self , binding , value , column_name ):

        # Here we're transforming from the value in the model to the dropdown's "selected" position
        model = self.drop_down_models[ column_name ]
        position = 0
        for row in model:
            if str( row.key ) == str( value ):
                return position
            position = position + 1
        return None

    def bind_dropdown_transform_from( self , binding , selected_position , column_name ):

        # Here we're transforming from the dropdown's "selected" position to a value
        model = self.drop_down_models[ column_name ]
        row = model[ selected_position ]
        value = row.key
        return value

class DatasheetWidget( Gtk.ScrolledWindow , Gtk4DbAbstract ):

    def __init__( self , column_definitions , data , drop_downs ):

        super().__init__()

        self.set_policy( Gtk.PolicyType.AUTOMATIC , Gtk.PolicyType.AUTOMATIC ) # horizontal , vertical
        self.set_vexpand( True )
        self.grid_row_class = None
        self.cv_width = 0
        self.drop_downs = drop_downs
        self.drop_down_models = {}
        self.setup_columns( column_definitions )
        self.model = self.generate_model( column_definitions , data )
        self.single_selection = Gtk.SingleSelection( model = self.model )
        self.cv.set_model( self.single_selection )
        self.set_child( self.cv )

        # TODO: Figure out how to apply this to everything underneath the Datasheet
        # self.css_provider = Gtk.CssProvider()
    #        self.css_provider.load_from_data( b"""columnview listview row cell {
    #                  padding-top: 2px;
    #                  padding-bottom: 2px;
    #                  padding-left: 2px;
    #                  padding-right: 2px;
    #                  border-left: 1px solid shade(#3c3f41, 1.2);
    #                  border-right: 1px solid shade(#3c3f41, 1.2);
    #                  border-top: 1px solid shade(#3c3f41, 1.2);
    #                  border-bottom: 1px solid shade(#3c3f41, 1.2);
    #                }
    #            """ )
    # self.add_custom_styling( self.cv )

        # self.connect( 'size-allocate' , self.on_container_size_allocate )
        # self.notify( "default-width" ).connect( self.on_container_size_allocate )
        GLib.timeout_add( 200 , self.queue_idle_resize_columns )

    def queue_idle_resize_columns( self ):

        GLib.idle_add( self.idle_resize_columns )
        return True

    def idle_resize_columns( self ):

        total_columnview_width = self.cv.get_width()
        if total_columnview_width == self.cv_width:
            return False

        self.cv_width = total_columnview_width

        available_width = total_columnview_width
        # subtract the width of the row state column
        available_width = available_width - self.row_state_column.get_fixed_width()

        # Loop over column definitions and subtract fixed-with columns
        for d in self._column_definitions:
            if 'x_absolute' in d.keys():
                available_width = available_width - d['x_absolute']

        # Now allocate the remaining space
        for d in self._column_definitions:
            if 'x_absolute' not in d.keys():
                if 'current_width' in d.keys():
                    this_width = d['current_width']
                else:
                    this_width = 0
                if d['type'] == 'hidden':
                    this_width = 0
                elif 'x_percent' in d.keys():
                    this_width = available_width / ( 100 / d['x_percent'] )
                d['current_width'] = this_width
                d['cvc'].set_fixed_width( this_width )

    def _add_widget_styling( self , widget ):
        if self.css_provider:
            context = widget.get_style_context()
            context.add_provider( self.css_provider , Gtk.STYLE_PROVIDER_PRIORITY_USER )

    def add_custom_styling( self , widget ):
        print( "add_custom_styling on {0}".format( widget ) )
        self._add_widget_styling( widget )
        # iterate children recursive
        for child in widget():
            self.add_custom_styling( child )

    def setup_columns( self , column_definitions ):

        self.cv = Gtk.ColumnView( hexpand=True , single_click_activate=False )

        # TODO: Setting single_click_activate=True above makes hovering with the mouse select a row
        # TODO: What we probably want is selecting a row when it's clicked in ( and not just in the record status image )

        # A column for the row_state ( # )

        f = Gtk.SignalListItemFactory()
        f.connect( "setup" , self.setup , 'image' , 1 , -1 , 'row_state' )
        f.connect( "bind" , self.bind , 'image' , 'row_state' )
        f.connect( "unbind" , self.unbind )

        cvc = Gtk.ColumnViewColumn( title = '#' , factory = f )
        cvc.set_fixed_width( 50 )
        self.cv.append_column( cvc )
        self.row_state_column = cvc

        for d in column_definitions:
            f = Gtk.SignalListItemFactory()
            f.connect( "setup" , self.setup , d['type'] , 1 , -1 , d['name'] )
            f.connect( "bind" , self.bind , d['type'] , d['name'] )
            f.connect( "unbind" , self.unbind )
            cvc = Gtk.ColumnViewColumn( title = d['name'] if d['type'] != 'hidden' else '' , factory = f )
            if 'x_absolute' in d.keys() and d['x_absolute']:
                cvc.set_fixed_width( d['x_absolute'] )
            self.cv.append_column( cvc )
            d['cvc'] = cvc

        self._column_definitions = column_definitions

    def setup( self , factory , item , type , xalign , chars , name ):

        if type == "label":
            widget = GridLabel( xalign=xalign , width_chars=chars , ellipsize=Pango.EllipsizeMode.END , valign=Gtk.Align.FILL , vexpand=True , column_name=name )
        elif type == "text" or type == "date" or type == "timestamp" or type == "hidden":
            widget = GridEntry( xalign=xalign , width_chars=chars , valign=Gtk.Align.FILL , vexpand=True , column_name=name )
        elif type == "drop_down":
            widget = GridDropDown( valign=Gtk.Align.FILL , vexpand=True , column_name=name )
        elif type == "image":
            widget = GridImage( column_name=name )
        else:
            raise Exception( "Unknown type: {0}".format( type ) )

        widget._binding = None
        item.set_child( widget )

    def bind( self , factory , item , type , column_name ):

        widget = item.get_child()
        grid_row = item.get_item()

        if type == "label":
            widget._binding = grid_row.bind_property( column_name , widget , "label" , GObject.BindingFlags.SYNC_CREATE )
        elif type == "text" or type == "date" or type == "timestamp" or type == 'hidden':
            widget._binding = grid_row.bind_property( column_name
                                                    , widget
                                                    , "text"
                                                    ,  GObject.BindingFlags.SYNC_CREATE
                                                     | GObject.BindingFlags.BIDIRECTIONAL
                                                    , self.bind_transform
                                                    )
        elif type == "drop_down":
            factory = self.drop_downs[ column_name ]['factory']
            model = self.drop_downs[ column_name ]['model']
            self.drop_down_models[ column_name ] = model
            # model = self.drop_down_models[ column_name ]
            widget.set_factory( factory )
            widget.set_model( model )
            widget._binding = grid_row.bind_property( column_name
                                                    , widget
                                                    , "selected"
                                                    ,  GObject.BindingFlags.SYNC_CREATE
                                                    | GObject.BindingFlags.BIDIRECTIONAL
                                                    , self.bind_dropdown_transform_to
                                                    , self.bind_dropdown_transform_from
                                                    , column_name
                                                    )
        elif type == "image":
            widget._binding = grid_row.bind_property( column_name , widget , "icon-name" , GObject.BindingFlags.SYNC_CREATE )
        else:
            raise Exception( "Unknown type {0}".format( type ) )

        widget.model_position = item.get_position()

    def bind_transform( self , binding , value ):

        return '' if value is None else value

    def unbind( self , factory , item ):

        widget = item.get_child()
        if widget._binding:
            widget._binding.unbind()
            widget._binding = None

    def column_name_to_number( self , column_name ):

        counter = 0
        for d in self._column_definitions:
            if d['name'] == column_name:
                return counter
            counter = counter + 1
        return False


class Gtk4PostgresAbstract( Gtk4DbAbstract ):

    """Postgres flavour of Gtk4DbAbstract"""

    def primary_key_info( self , db=None , schema=None , table=None ):

        cursor = self.connection.cursor()

        sql = """SELECT
                  a.attname,
                  format_type(a.atttypid, a.atttypmod) 
                FROM
                  pg_attribute a
                  JOIN (SELECT *, GENERATE_SUBSCRIPTS(indkey, 1) AS indkey_subscript FROM pg_index) AS i
                    ON
                      i.indisprimary
                      AND i.indrelid = a.attrelid
                      AND a.attnum = i.indkey[i.indkey_subscript]
                WHERE
                  a.attrelid = %(table_name)s::regclass
                ORDER BY
                  i.indkey_subscript"""

        self.execute( cursor , sql , { "table_name": table } )

        columns = []

        for record in self.fetchrow_dict( cursor ):
            columns.append( record['attname'] )

        return columns

    def column_names_from_cursor( self , cursor ):

        """This is tragic, but Python's database API is not consistent across database backends
           ( unlike stable languages like Perl ), so each subclass must define this method to return
           a list of column names from an active cursor."""

        return [desc[0] for desc in cursor.description]

    # def execute( self , cursor , sql , params={} ):
    #
    #     # import psycopg2
    #
    #     start_time = time.time()
    #
    #     try:
    #         if len( params ) == 0:
    #             cursor.execute( sql )
    #         else:
    #             cursor.execute( sql , params )
    #     # except psycopg2.OperationalError as e:
    #     #     raise e
    #     except Exception as e:
    #         raise e
    #
    #     end_time = time.time()
    #     print( "execute() completed in {0} seconds".format( round( end_time - start_time ) , 2 ) )

    def last_insert_id( self , cursor ):

        cursor.execute('SELECT LASTVAL()')
        return cursor.fetchone()[0]

    def _db_prepare_insert_column_fragment( self , column_definition , column_name ):

        # Prepare a placeholder string for insert statements statements ( usually just a: %s )
        # Sub-classes can do things like apply formatting or functions, eg Oracle
        # has to call to_date() for values going into date columns

        if column_definition['type'] == "date" or column_definition['type'] == "timestamp":
            return "cast( nullif( %s, '' ) as timestamp )"
        else:
            return "%s"

    def _db_prepare_update_column_fragment( self , column_definition , column_name ):

        # Each value in our insert/update statements goes through this method.
        # Sub-classes can do things like apply formatting or functions, eg Oracle
        # has to call to_date() for values going into date columns

        if column_definition['type'] == "timestamp":
            return "{0} = cast( nullif( %s , '' ) as timestamp )".format( column_name )
        else:
            return "{0} = %s".format( column_name )

    def fetch_column_info( self , cursor ):

        column_info = {}
        for i in cursor.description:
            this = { 'name': i.name , 'type_code': i.type_code }
            if i.type_code == 1114:
                this['type'] = "timestamp"
            else:
                this['type'] = "text"
            column_info[ i.name ] = this
        return column_info


class Gtk4SnowflakeAbstract( Gtk4DbAbstract ):

    """Snowflake flavour of Gtk4DbAbstract"""

    def primary_key_info( self , db=None , schema=None , table=None ):

        # TODO - implement
        cursor = self.connection.cursor()

        sql = """SELECT
                  a.attname,
                  format_type(a.atttypid, a.atttypmod) 
                FROM
                  pg_attribute a
                  JOIN (SELECT *, GENERATE_SUBSCRIPTS(indkey, 1) AS indkey_subscript FROM pg_index) AS i
                    ON
                      i.indisprimary
                      AND i.indrelid = a.attrelid
                      AND a.attnum = i.indkey[i.indkey_subscript]
                WHERE
                  a.attrelid = %(table_name)s::regclass
                ORDER BY
                  i.indkey_subscript"""

        self.execute( cursor , sql , { "table_name": table } )

        columns = []

        for record in self.fetchrow_dict( cursor ):
            columns.append( record['attname'] )

        return columns

    def column_names_from_cursor( self , cursor ):

        """This is tragic, but Python's database API is not consistent across database backends
           ( unlike stable languages like Perl ), so each subclass must define this method to return
           a list of column names from an active cursor."""

        return [desc[0] for desc in cursor.description]

    def last_insert_id( self , cursor ):

        cursor.execute('SELECT LASTVAL()')
        return cursor.fetchone()[0]

    def _db_prepare_insert_column_fragment( self , column_definition , column_name ):

        # Prepare a placeholder string for insert statements statements ( usually just a: %s )
        # Sub-classes can do things like apply formatting or functions, eg Oracle
        # has to call to_date() for values going into date columns

        if column_definition['type'] == "date" or column_definition['type'] == "timestamp":
            return "cast( nullif( %s, '' ) as timestamp )"
        else:
            return "%s"

    def _db_prepare_update_column_fragment( self , column_definition , column_name ):

        # Each value in our insert/update statements goes through this method.
        # Sub-classes can do things like apply formatting or functions, eg Oracle
        # has to call to_date() for values going into date columns

        if column_definition['type'] == "timestamp":
            return "{0} = cast( nullif( %s , '' ) as timestamp )".format( column_name )
        else:
            return "{0} = %s".format( column_name )

    def fetch_column_info( self , cursor ):

        column_info = {}
        for i in cursor.description:
            this = { 'name': i.name , 'type_code': i.type_code }
            if i.type_code == 1114:
                this['type'] = "timestamp"
            else:
                this['type'] = "text"
            column_info[ i.name ] = this
        return column_info


class Gtk4MySQLAbstract( Gtk4DbAbstract ):

    """MySQL flavour of Gtk4DbAbstract"""

    def last_insert_id( self , cursor ):

        return cursor.lastrowid

    def primary_key_info( self , db=None , schema=None , table=None ):

        # TODO
        columns = []
        return columns

    def column_names_from_cursor( self , cursor ):

        """This is tragic, but Python's database API is not consistent across database backends
           ( unlike stable languages like Perl ), so each subclass must define this method to return
           a list of column names from an active cursor."""

        return cursor.column_names

    def fetch_column_info( self , cursor ):

        column_info = {}
        for i in cursor.description:
            this = { 'name': i[0] , 'type_code': i[1] }
            if i[1] == 12:
                this['type'] = "timestamp"
            else:
                this['type'] = "text"
            column_info[ i[0] ] = this
        return column_info

    def primary_key_info( self , db=None , schema=None , table=None ):

        cursor = self.connection.cursor()

        sql = """select
                         column_name
                 from
                         information_schema.table_constraints t
                 join    information_schema.key_column_usage  k
                                                                  using ( constraint_name , table_schema , table_name )
                 where
                         t.constraint_type = 'PRIMARY KEY'
                 and     t.table_schema = %(table_schema)s
                 and     t.table_name = %(table_name)s
                 order by
                         table_name , constraint_name , ordinal_position"""

        self.execute( cursor , sql , { "table_schema": self.connection.database ,  "table_name": table } )

        columns = []

        for record in self.fetchrow_dict( cursor ):
            columns.append( record['column_name'] )

        return columns

    def _db_prepare_insert_column_fragment( self , column_definition , column_name ):

        # Prepare a placeholder string for insert statements statements ( usually just a: %s )
        # Sub-classes can do things like apply formatting or functions, eg Oracle
        # has to call to_date() for values going into date columns

        if column_definition['type'] == "date" or column_definition['type'] == "timestamp":
            return "nullif( %s, '' )"
        else:
            return "%s"

    def _db_prepare_update_column_fragment( self , column_definition , column_name ):

        # Each value in our insert/update statements goes through this method.
        # Sub-classes can do things like apply formatting or functions, eg Oracle
        # has to call to_date() for values going into date columns

        if column_definition['type'] == "timestamp":
            return "{0} = nullif( %s , '' )".format( column_name )
        else:
            return "{0} = %s".format( column_name )


class Gtk4SQLiteAbstract( Gtk4DbAbstract ):

    """Postgres flavour of Gtk4DbAbstract"""

    def primary_key_info( self , db=None , schema=None , table=None ):

        cursor = self.connection.cursor()

        sql = "select i.name from pragma_table_info( ? ) as i where i.pk > 0 order by i.pk"

        self.execute( cursor , sql , [ ( table ) ] )

        columns = []

        for record in self.fetchrow_dict( cursor ):
            # print( record )
            columns.append( record['name'] )

        return columns

    def column_names_from_cursor( self , cursor ):

        """This is tragic, but Python's database API is not consistent across database backends
           ( unlike stable languages like Perl ), so each subclass must define this method to return
           a list of column names from an active cursor."""

        return [desc[0] for desc in cursor.description]

    def last_insert_id( self , cursor ):

        cursor.execute( 'select last_insert_rowid()' )
        return cursor.fetchone()[0]

    def _db_prepare_insert_column_fragment( self , column_definition , column_name ):

        # Prepare a placeholder string for insert statements statements ( usually just a: %s )
        # Sub-classes can do things like apply formatting or functions, eg Oracle
        # has to call to_date() for values going into date columns

        if column_definition['type'] == "date" or column_definition['type'] == "timestamp":
            return "cast( nullif( ?, '' ) as timestamp )"
        else:
            return "?"

    def _db_prepare_update_column_fragment( self , column_definition , column_name ):

        # Each value in our insert/update statements goes through this method.
        # Sub-classes can do things like apply formatting or functions, eg Oracle
        # has to call to_date() for values going into date columns

        if column_definition['type'] == "timestamp":
            return "{0} = cast( nullif( ? , '' ) as timestamp )".format( column_name )
        else:
            return "{0} = ?".format( column_name )

    def fetch_column_info( self , cursor ):

        # Python's DB API is a joke compared to Perl. FFS ...
        column_info = {}
        for i in cursor.description:
            # print( "\n\n{0}".format( i ) )
            column_info[ i[0] ] = { 'name': i[0] , 'type_code': None , 'type': 'text' }
        return column_info


class Gtk4OracleAbstract( Gtk4DbAbstract ):

    """Oracle flavour of Gtk4DbAbstract"""

    def _db_prepare_update_column_fragment( self , column_definition , column_name ):

        # Each value in our insert/update statements goes through this method.
        # Sub-classes can do things like apply formatting or functions, eg Oracle
        # has to call to_date() for values going into date columns

        if column_definition['type'] == "date":
            return "{0} = to_date( ? )".format( column_name )
        else:
            return "{0} = ?".format( column_name )

    def _db_prepare_insert_column_fragment( self , column_definition , column_name ):

        # Prepare a placeholder string for insert statements statements ( usually just a: ? )
        # Sub-classes can do things like apply formatting or functions, eg Oracle
        # has to call to_date() for values going into date columns

        if column_definition['type'] == "date":
            return "to_date( %s, 'yyyy-mm-dd' )"
        else:
            return "%s"


##############################################################################################################
# Datasheet logic
class Gtk4DbDatasheet( Gtk4DbAbstract ):

    """This class implements a user-editable records manager, based on a database configuration ( connection, table ).
    Records are rendered in a liststore, and users can be presented with insert,delete,undo,apply buttons."""

    @staticmethod
    def generator( connection=None , **kwargs ):

        if not connection:
            raise Exception( "factory function wasn't passed a connection" )
        else:
            db_name_map = {
                'psycopg': 'Postgres'
              , 'psycopg2': 'Postgres'
              , 'psycopg3': 'Postgres'
              , 'mysql': 'MySQL'
              , 'sqlite3': 'SQLite'
              , 'sqlite': 'SQLite'
              , 'snowflake': 'Snowflake'
            }
            mod = connection.__class__.__module__.split( '.' , 1 )[0]
            print( "Found: [{0}]".format( mod ) )
            db_type = db_name_map.get( mod )
            target_class = "Gtk4{0}Datasheet".format( db_type )
            if db_type == "Postgres":
                return Gtk4PostgresDatasheet( connection=connection , **kwargs )
            elif db_type == "MySQL":
                return Gtk4MySQLDatasheet( connection=connection , **kwargs )
            elif db_type == "SQLite":
                return Gtk4SQLiteDatasheet( connection=connection , **kwargs )
            elif db_type == "Snowflake":
                return Gtk4SnowflakeDatasheet( connection=connection , **kwargs )
            else:
                raise Exception( "Unsupported database type: {0}".format( target_class ) )

    def __init__( self, read_only=False, auto_apply=False, data_lock_field = None
                 , dont_update_keys=False, auto_incrementing=True, on_apply=False
                 , sw_no_scroll=False, dump_on_error=False, no_auto_tools_box=False
                 , before_apply=False, custom_changed_text = '', friendly_table_name=''
                 , quiet=False, recordset_items=None, on_row_select=None
                 , before_insert=None, on_insert=None
                 , drop_downs={}, **kwargs ):

        if recordset_items is None:
            recordset_items = ["insert", "undo", "delete", "apply", "data_to_csv"]

        self.recordset_items = recordset_items

        for i in [ "connection" , "sql" , "box" ]:
            if i not in kwargs.keys():
                raise Exception( "Gtk4DbDatasheet constructor missing {0}".format(i) )

        self.supported_recordset_items = {
            "insert":         { "type": "button" , "icon_name": "document-new" }
          , "undo":           { "type": "button" , "icon_name": "edit-undo" }
          , "delete":         { "type": "button" , "icon_name": "edit-delete" }
          , "apply":          { "type": "button" , "icon_name": "document-save" }
          , "data_to_csv":    { "type": "button" , "icon_name": "document-save-as" }
        }

        # Set a few things that need to be in place early ...
        self.read_only = read_only
        self.auto_apply = auto_apply
        self.data_lock_field = data_lock_field
        self.dont_update_keys = dont_update_keys
        self.auto_incrementing = auto_incrementing
        self.sw_no_scroll = sw_no_scroll
        self.on_apply = on_apply
        self.before_apply = before_apply
        self.changed_signal = None
        self.on_row_select = on_row_select
        self.row_select_signal = None
        self.footer = None
        self.after_query = None
        self.cursor_ids = {}
        self.fields_setup = False
        self.fields = []
        self.column_name_to_number_mapping = {}
        self.dump_on_error = dump_on_error
        self.no_auto_tools_box = no_auto_tools_box
        self.custom_changed_text = custom_changed_text
        self.datasheet = {}
        self.new_where_dict = {}
        self.quiet = quiet
        self.column_info = {}
        self.widget_setup = False
        self.spinner = None
        self.current_track = None
        self.before_insert = before_insert
        self.on_insert = on_insert
        self.child_foreign_key_binders = []
        self.foreign_key_binder = None
        self.drop_downs = drop_downs
        self.drop_down_models = {}

        for i in kwargs.keys():
            setattr( self , i , kwargs[i] )

        for drop_down in drop_downs:
            factory , model = self.setup_drop_down_factory_and_model(
                drop_downs[ drop_down ]['sql']
              , drop_downs[ drop_down ]['bind_values']
            )
            drop_downs[ drop_down ]['model'] = model
            self.drop_down_models[ drop_down ] = model
            drop_downs[ drop_down ]['factory'] = factory

        self.drop_downs = drop_downs

        if not len( friendly_table_name ):
            if 'from' in self.sql.keys():
                self.friendly_table_name = self.sql['from']
            else:
                self.friendly_table_name = self.sql['pass_through']
        else:
            self.friendly_table_name = friendly_table_name

        if not self.query():
            return

        if not self.no_auto_tools_box:
            self.recordset_tools_box = Gtk.Box( orientation = Gtk.Orientation.HORIZONTAL , spacing = 5 )
            self.recordset_tools_box.set_hexpand( True )
            self.recordset_tools_box.set_homogeneous( True )
            self.box.append( self.recordset_tools_box )
        else:
            self.recordset_tools_box = None

        if self.recordset_tools_box:
            self.setup_recordset_tools()

        # To avoid data-loss when a window is closed, we need to hook into the window's close_request signal,
        # check for changes, and raise a dialog asking the user to apply outstanding changes
        parent_widget = self.datasheet.get_parent()
        while parent_widget:
            toplevel_widget = parent_widget
            parent_widget = toplevel_widget.get_parent()
        toplevel_widget.connect( 'close_request' , self.on_toplevel_closed )

        self.window = toplevel_widget

    def destroy( self ):

        child = self.box.get_first_child()
        while child:
            self.box.remove( child )
            child = self.box.get_next_sibling()

        self.datasheet = None
        self.widget_setup = False

    def get_current_grid_row( self ):

        position = self.datasheet.single_selection.get_selected()
        grid_row = self.datasheet.single_selection[ position ]
        return grid_row

    def get( self , column_name ):

        grid_row = self.get_current_grid_row()
        return getattr( grid_row , column_name )

    def set( self , column_name , value ):

        grid_row = self.get_current_grid_row()
        setattr( grid_row , column_name , value )

    def selection_changed_handler( self , selection, first_item_changed, no_of_items_changed ):

        if self.on_row_select or len( self.child_foreign_key_binders ):
            """If ther'es nothing in the model, select.get_selected() STILL returns an int
                  ... and this will make selection[ position ] below fail on a list index error"""
            try:
                position = selection.get_selected()
                grid_row = selection[ position ]
                if grid_row.track() != self.current_track:
                    for fkb in self.child_foreign_key_binders:
                        self.sync_grid_row_to_foreign_key_binding( grid_row , fkb )
                    self.current_track = grid_row.track()
                    if self.on_row_select:
                        self.on_row_select( grid_row )
            except:
                """If the position appears to be invalid, assume the model is empty. In this case,
                   we want to refresh FKBs with None instead of a grid_row ... ie empty them"""
                for fkb in self.child_foreign_key_binders:
                    self.sync_grid_row_to_foreign_key_binding( None , fkb )
                self.current_track = None


    def sync_grid_row_to_foreign_key_binding( self , grid_row , foreign_key_binding ):
            """
              Here we assemble a keys dict and call the foreign key binder's setter method,
              which will trigger a child requery.
              This is a separate method, which is called from above, and also when
              setting up the binding initially
            """
            keys_dict = {}
            for this_mapping in foreign_key_binding.mapping:
                if grid_row:
                    keys_dict[ this_mapping['target'] ] = getattr( grid_row , this_mapping['source'] )
                else:
                    keys_dict[ this_mapping['target'] ] = None
            setattr( foreign_key_binding , 'keys_dict_json' , json.dumps( keys_dict ) )

    def _do_query( self ):

        if self.datasheet:
            self.box.remove( self.datasheet )

        """We need to reset the current track, or we can miss handling row-selected events
          ( eg if the 1st row was selected, and we request, and again the 1st row is selected )"""
        self.current_track = None
        cursor = super()._do_query()

        if not self.setup_fields():
            return None

        self.datasheet = DatasheetWidget( self.fields , cursor , self.drop_downs )

        """We need these back at this level, and not in the DatasheetWidget, for things to work in a generic way"""
        self.grid_row_class = self.datasheet.grid_row_class
        self.model = self.datasheet.model
        self.box.prepend( self.datasheet )
        self.widget_setup = True
        self.row_select_signal = self.datasheet.cv.get_model().connect( 'selection-changed' , self.selection_changed_handler )

        """As the datasheet is already populated at this point we've missed the 1st selection-changed signal,
           so we trigger it now"""
        self.selection_changed_handler( self.datasheet.single_selection , 0 , 1 )

        if self.after_query:
            self.after_query()

        return True

    def apply( self , *args ):

        if self.read_only:
            self.dialog(
                title="Read Only!"
              , type="warning"
              , text="Datasheet is open in read-only mode!"
            )
            return False

        row_numbers_to_delete = []
        row_number = -1
        model = self.datasheet.cv.get_model()

        for row in model:
            if not row: # Happens when we delete rows
                continue
            row_number = row_number + 1
            state = row.row_state
            # Decide what to do based on status
            if state == UNCHANGED or state == LOCKED:
                continue

            # Now assemble a hash of primary key items and values.
            # This gets passed to any before_apply() and after_apply() handlers.
            primary_keys = {}
            for primary_key_item in self.primary_keys:
                primary_keys[ primary_key_item ] = getattr( row , primary_key_item )

            if self.before_apply:
                # Better change the state indicator back into text, rather than make
                # people use our constants. I think, anyway ...
                state_txt = ""
                if state         == INSERTED:
                    state_txt     = "inserted"
                elif state       == CHANGED:
                    state_txt     = "changed"
                elif state       == DELETED:
                    state_txt     = "deleted"
                # Do people want the whole row? I don't. Maybe others would? Wait for requests...
                result = self.before_apply(
                    status=state_txt
                  , primary_keys=primary_keys
                  , grid_row=row
                )
                # If the user-defined before_apply() function returns False, we abort this
                # update and continue with the next
                if not result:
                    continue
            if state == DELETED:
                if not self._do_delete( row=row ):
                    return False
                # If we removed rows while in a for loop of the model, very strange things happen ...
                row_numbers_to_delete.append( row_number )
            elif state == INSERTED: # We process the insert / update operations in a similar fashion
                if not self._do_insert( row=row ):
                    return False
            elif state == CHANGED:
                if not self._do_update( row=row ):
                    return False

            # Execute user-defined functions
            if self.on_apply:
                # Better change the status indicator back into text, rather than make
                # people use our constants. I think, anyway ...
                status_txt = ""
                if state         == INSERTED:
                    state_txt     = "inserted"
                elif state       == CHANGED:
                    state_txt    = "changed"
                elif state       == DELETED:
                    state_txt     = "deleted"
                self.on_apply(
                    state=state_txt
                  , primary_keys=primary_keys
                  , grid_row=row
                )

        if len( row_numbers_to_delete ):
            # Each time we remove an item, we have to subtract 1 from the remaining indices
            removed = 0
            for i in row_numbers_to_delete:
                model.get_model().remove( i - removed )
                removed = removed + 1

        return True

    def insert( self , button , row_state = INSERTED , columns_and_values = {} , *args ):

        if not super().insert( button , row_state = row_state , columns_and_values = columns_and_values , *args ):
            return

        model_size = len( self.model )
        self.datasheet.single_selection.set_selected( model_size - 1 )

    def upsert_key( self , column_name , value ):

        print( "upsert_key() not implemented!" )

    def delete( self , *args ):

        # single_selection = self.datasheet.cv.get_model()
        position = self.datasheet.single_selection.get_selected()
        grid_row = self.datasheet.single_selection[ position ]
        grid_row.row_state = DELETED

    def lock( self , *args ):

        print( "lock() not implemented!" )

    def unlock( self , *args ):

        print( "unlock() not implemented!" )

    def replace_combo_model( self , column_no, model ):

        # This function replaces a *normal* combo ( NOT a dynamic one ) with a new one
        column = self.treeview.get_column( column_no )
        renderer = ( column.get_cells )[0]
        renderer.set( "model" , model )

        return True

    def create_dynamic_model( self , model_setup, data ):

        # This function accepts a combo definition and a row of data ( *MINUS* the record status column ),
        # and creates a combo model to insert back into the main TreeView's model
        # We currently only support a model with 2 columns: an ID column and a Display column

        # TODO create_dynamic_model: Support adding more columns to the model

        print( "create_dynamic_model() not implemented!" )

    def setup_combo( self , combo_name ):

        print( "setup_combo() not implemented!" )

    def any_changes( self ):

        model = self.datasheet.cv.get_model()
        for row in model:
            state = row.row_state
            if state != UNCHANGED and state != LOCKED:
                return True
        return False

    def sum_column( self , column_no, conditions ):

        # This function returns the sum of all values in the given column
        print( "sum_column() not implemented!" )

    def max_column( self , column_no ):

        # This function returns the MAXIMUM value in a given column
        print( "max_column() not implemented!" )

    def average_column( self , column_no ):

        # This function returns the AVERAGE value in a given column
        print( "average_column() not implemented!" )

    def count( self , column_no , conditions ):

        # This function returns the number of all records ( optionally where $column_no matches $conditions )
        print( "count() not implemented!" )


##############################################################################################################
# Form logic
class Gtk4DbForm( Gtk4DbAbstract ):

    """This class implements a user-editable records manager, based on a database configuration ( connection, table ).
    Records are rendered in a liststore, and users can be presented with insert,delete,undo,apply buttons."""

    @staticmethod
    def generator( connection=None , **kwargs ):

        if not connection:
            raise Exception( "factory function wasn't passed a connection" )
        else:
            db_name_map = {
                'psycopg': 'Postgres'
              , 'psycopg2': 'Postgres'
              , 'psycopg3': 'Postgres'
              , 'mysql':    'MySQL'
              , 'sqlite3':  'SQLite'
              , 'sqlite':   'SQLite'
            }
            mod = connection.__class__.__module__.split( '.' , 1 )[0]
            # print( "Found: [{0}]".format( mod ) )
            db_type = db_name_map.get( mod )
            target_class = "Gtk4{0}Form".format( db_type )
            if db_type == "Postgres":
                return Gtk4PostgresForm( connection=connection , **kwargs )
            elif db_type == "MySQL":
                return Gtk4MySQLForm( connection=connection , **kwargs )
            elif db_type == 'SQLite':
                return Gtk4SQLiteForm( connection=connection, **kwargs )
            else:
                raise Exception( "Unsupported database type: {0}".format( target_class ) )

    def __init__( self , connection = None , sql = {} , builder=None , read_only=False , auto_apply=False , data_lock_field = None
                  , dont_update_keys=False , auto_incrementing=True , on_apply=False , sw_no_scroll=False , dump_on_error=False
                  , auto_tools_box = None , before_apply=False , custom_changed_text = '' , friendly_table_name=''
                  , recordset_tools_box = None , recordset_items = None , quiet=False, widget_prefix=None
                  , css_provider = None , before_insert = False , on_insert = False , drop_downs = {} ):

        if recordset_items is None:
            recordset_items = [ "spinner" , "status" , "insert" , "undo" , "delete" , "apply" ]

        self.recordset_items = recordset_items

        # for i in [ "connection" , "sql" , "builder" ]:
        #     if i not in kwargs.keys():
        #         raise Exception( "Gtk4DbForm constructor missing {0}".format(i) )

        self.supported_recordset_items = {
            "spinner":        { "type": "spinbutton" }
          , "status":         { "type": "label" }
          , "insert":         { "type": "button" , "icon_name": "document-new" }
          , "undo":           { "type": "button" , "icon_name": "edit-undo" }
          , "delete":         { "type": "button" , "icon_name": "edit-delete" }
          , "apply":          { "type": "button" , "icon_name": "document-save" }
          , "data_to_csv":    { "type": "button" , "icon_name": "document-save-as" }
        }

        # Set a few things that need to be in place early ...
        self.builder = builder
        self.sql = sql
        self.connection = connection
        self.recordset_tools_box = recordset_tools_box
        self.read_only = read_only
        self.auto_apply = auto_apply
        self.data_lock_field = data_lock_field
        self.dont_update_keys = dont_update_keys
        self.auto_incrementing = auto_incrementing
        self.on_apply = on_apply
        self.before_apply = before_apply
        self.before_insert = before_insert
        self.on_insert = on_insert
        self.changed_signal = None

        self.after_query = None
        self.cursor_ids = {}
        self.fields_setup = False
        self.fields = []
        self.column_name_to_number_mapping = {}
        self.dump_on_error = dump_on_error
        self.auto_tools_box = auto_tools_box
        self.custom_changed_text = custom_changed_text
        self.datasheet = {}
        self.new_where_dict = {}
        self.quiet = quiet
        self.column_info = {}
        self.widget_setup = False
        self.spinner = None
        self.widget_prefix = widget_prefix
        self.css_provider = css_provider
        self.model_to_widget_bindings = {}
        self.drop_down_models = {}
        self.child_foreign_key_binders = []
        self.foreign_key_binder = None
        self.drop_downs = drop_downs

        red_frame_css = """
        entry.red-frame {
            padding: 9px;
            border: 3px solid red;
            border-radius: 9px;
        }
        """

        self.css_provider.load_from_string( red_frame_css )
        d = Gdk.Display.get_default()
        Gtk.StyleContext.add_provider_for_display( d, self.css_provider , Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION )

        # for i in kwargs.keys():
        #     setattr( self , i , kwargs[i] )

        if not len( friendly_table_name ):
            self.friendly_table_name = self.sql['from']
        else:
            self.friendly_table_name = friendly_table_name

        if self.auto_tools_box:
            self.recordset_tools_box = Gtk.Box( orientation = Gtk.Orientation.HORIZONTAL , spacing = 5 )
            self.recordset_tools_box.set_hexpand( True )
            self.recordset_tools_box.set_homogeneous( True )
            self.auto_tools_box.append( self.recordset_tools_box )

        if self.recordset_tools_box:
            self.setup_recordset_tools()

        # self.drop_downs is a dictionary, with keys being column names, and values being a dictionary
        # defining some sql and bind values to set up the drop down
        for drop_down in self.drop_downs:
            self.setup_drop_down( drop_down , self.drop_downs[ drop_down ][ 'sql' ] , self.drop_downs[ drop_down ][ 'bind_values' ] )

        if not self.query():
            return

        # To avoid data-loss when a window is closed, we need to hook into the window's close_request signal,
        # check for changes, and raise a dialog asking the user to apply outstanding changes
        for widget in self.builder.get_objects():
            if isinstance( widget , Gtk.Window ):
                widget.connect( 'close_request' , self.on_toplevel_closed )
                self.window = widget
                return

    def setup_drop_down( self , column_name , sql , bind_values ):

        factory , model = self.setup_drop_down_factory_and_model( sql , bind_values )
        drop_down = self.get_widget( column_name )
        drop_down.set_factory( factory )
        drop_down.set_model( model )
        self.drop_down_models[ column_name ] = model

    def get_widget( self , column_name , missing_is_fatal = True ):

        widget_name = ( self.widget_prefix if self.widget_prefix else '' ) + column_name
        widget = self.builder.get_object( widget_name )
        if widget is None and missing_is_fatal:
            raise Exception( "get_widget() called with column name [{0}] which resolved to [{1}]" \
                             " but none was found in the Gtk.Builder object".format( column_name , widget_name ) )
        return widget

    def get( self , column_name ):

        return getattr( self.model , column_name )

    def set( self , column_name , value ):

        setattr( self.model , column_name , value )

    def _do_query( self ):

        cursor = super()._do_query()

        if not self.setup_fields():
            return None

        self.position = 0
        self.model = self.generate_model( self.fields , cursor )
        # If the query returned 0 records, we still want a ( blank ) record
        if not len( self.model ):
            self.insert( None , row_state=UNCHANGED )
        self.move( 0 , 0 )
        self.widget_setup = True
        self.set_spinner_range()

        if self.after_query:
            self.after_query()

        return True

    # def __init__( self , column_definitions , data ):
    #
    #     super().__init__()
    #
    #     self.grid_row_class = None


    def move( self , offset = None , absolute = None ):

        if offset is not None:
            if len( self.model ) > self.position + offset:
                self.position = 0
            else:
                self.position = self.position + offset
                if self.position < 0:
                    self.position = 0
        else:
            if absolute > len( self.model ):
                self.position = len( self.model )
            else:
                self.position = absolute

        self.bind_model_to_widgets()

    def bind_model_to_widgets( self ):

        for column in self.model_to_widget_bindings.keys():
            self.model_to_widget_bindings[ column ].unbind()

        this_grid_row = self.model[ self.position ]


        # for each column in model:
        # - check if a widget exists
        # - bind via bind_property() method, ie:
        #   https://stackoverflow.com/questions/67763050/how-to-do-2-way-data-binding-using-pythonpygobjects-gobject-bind-property-func
        for column_name in self.fieldlist:
            widget = self.get_widget( column_name )
            if widget:
                if isinstance( widget , Gtk.Calendar ):
                    # This won't work, as Gtk.Calendar doesn't have a fucking 'date' property.
                    # The date is broken out into day, month, year. We need to update the grid_row model
                    # to contain these, and bind to each separately. This requires using Gtk Expressions, apparently
                    # https://discourse.gnome.org/t/gtk-propertyexpression-new-return-null-gtk4-python/19384
                    # Not sure how setting these 3 separately will work?
                    # self.model_to_widget_bindings.append(
                    #     this_grid_row.bind_property( column_name , widget , "date" , GObject.BindingFlags.BIDIRECTIONAL
                    #                                  | GObject.BindingFlags.SYNC_CREATE )
                    # )
                    print( "Widget [ {0} ] - Gtk.Calendar is not supported, because it doesn't have a 'date' property".format( column_name ) )
                elif isinstance( widget , Gtk.DropDown ):
                    self.model_to_widget_bindings[ column_name ] = this_grid_row.bind_property(
                                                                       column_name , widget , "selected"
                                                                     , GObject.BindingFlags.BIDIRECTIONAL
                                                                     | GObject.BindingFlags.SYNC_CREATE
                                                                     , self.bind_dropdown_transform_to
                                                                     , self.bind_dropdown_transform_from
                                                                     , column_name
                                                                   )
                else:
                    self.model_to_widget_bindings[ column_name ] = this_grid_row.bind_property(
                                                                       column_name , widget , "text"
                                                                     , GObject.BindingFlags.BIDIRECTIONAL
                                                                     | GObject.BindingFlags.SYNC_CREATE
                                                                     , self.bind_transform_to )
                    signal = this_grid_row.connect( 'notify' , self.handle_grid_notify )

    def bind_transform_to( self , binding , value ):

        return '' if value is None else value

    def handle_grid_notify( self , grid_row , param_spec ):
        notify_topic = param_spec.name
        if notify_topic != 'row-state':
            # Assume the topic is a column name at this point
            current_value = getattr( grid_row , notify_topic )
            widget = self.get_widget( notify_topic )
            if current_value is not None:
                widget.add_css_class( 'red-frame' )
            else:
                widget.remove_css_class( 'red-frame' )

    def destroy( self ):

        for set in self.objects_and_signals:
            set[0].signal_handler_disconnect( set[1] )

        # TODO: push this signal onto our objects_and_signals so we don't have to do this ... but how do we remove
        if self.changed_signal:
            self.treeview.get_model().signal_handler_disconnect( self.changed_signal )

        self.destroy_recordset_tools()

        if self.box:
            for i in self.box.get_children():
                i.destroy()

    def any_changes( self ):

        row = self.model[ self.position ]
        state = row.row_state
        if state == UNCHANGED or state == LOCKED:
            return False
        else:
            return True

    def apply( self , *args ):

        if self.read_only:
            self.dialog(
                title="Read Only!"
              , type="warning"
              , text="Datasheet is open in read-only mode!"
            )
            return False

        row = self.model[ self.position ]
        state = row.row_state
        # Decide what to do based on status
        if state == UNCHANGED or state == LOCKED:
            return True

        # Now assemble a hash of primary key items and values.
        # This gets passed to any before_apply() and after_apply() handlers.
        primary_keys = {}
        for primary_key_item in self.primary_keys:
            primary_keys[ primary_key_item ] = getattr( row , primary_key_item )

        if self.before_apply:
            # Better change the state indicator back into text, rather than make
            # people use our constants. I think, anyway ...
            state_txt = ""
            if state         == INSERTED:
                state_txt     = "inserted"
            elif state       == CHANGED:
                state_txt     = "changed"
            elif state       == DELETED:
                state_txt     = "deleted"
            # Do people want the whole row? I don't. Maybe others would? Wait for requests...
            result = self.before_apply(
                status=state_txt
              , primary_keys=primary_keys
              , grid_row=row
            )
            # If the user-defined before_apply() function returns False, we abort this
            # update and continue with the next
            if not result:
                return

        if state == DELETED:
            if not self._do_delete( row=row ):
                return False
        elif state == INSERTED: # We process the insert / update operations in a similar fashion
            if not self._do_insert( row=row ):
                return False
        elif state == CHANGED:
            if not self._do_update( row=row ):
                return False

        # Execute user-defined functions
        if self.on_apply:
            # Better change the status indicator back into text, rather than make
            # people use our constants. I think, anyway ...
            status_txt = ""
            if state         == INSERTED:
                state_txt     = "inserted"
            elif state       == CHANGED:
                state_txt    = "changed"
            elif state       == DELETED:
                state_txt     = "deleted"
            self.on_apply(
                state=state_txt
              , primary_keys=primary_keys
              , grid_row=row
            )

        return True

    def insert( self , button , row_state = INSERTED , columns_and_values = {} , *args ):

        if not super().insert( button , row_state = row_state , columns_and_values = {} , *args ):
            return

        self.move( len( self.model ) - 1 )

    def upsert_key( self , column_name , value ):

        print( "upsert_key() not implemented!" )

    def delete( self , *args ):

        # single_selection = self.datasheet.cv.get_model()
        position = self.single_selection.get_selected()
        grid_row = self.single_selection[ position ]
        grid_row.row_state = DELETED


##############################################################################################################
# Datasheet flavours
class Gtk4PostgresDatasheet( Gtk4PostgresAbstract , Gtk4DbDatasheet ):

    def __init__( self , read_only=False , auto_apply=False , **kwargs ):
        super( Gtk4PostgresDatasheet , self ).__init__( read_only=read_only , auto_apply=auto_apply , **kwargs )


class Gtk4MySQLDatasheet( Gtk4MySQLAbstract , Gtk4DbDatasheet ):

    def __init__( self , read_only=False , auto_apply=False , **kwargs ):
        super( Gtk4MySQLDatasheet , self ).__init__( read_only=read_only , auto_apply=auto_apply , **kwargs )


class Gtk4SQLiteDatasheet( Gtk4SQLiteAbstract , Gtk4DbDatasheet ):

    def __init__( self , read_only=False , auto_apply=False , **kwargs ):
        super( Gtk4SQLiteDatasheet , self ).__init__( read_only=read_only , auto_apply=auto_apply , **kwargs )

class Gtk4SnowflakeDatasheet( Gtk4SnowflakeAbstract , Gtk4DbDatasheet ):

    def __init__( self , read_only=False , auto_apply=False , **kwargs ):
        super( Gtk4SnowflakeDatasheet , self ).__init__( read_only=read_only , auto_apply=auto_apply , **kwargs )

class Gtk4OracleDatasheet( Gtk4OracleAbstract , Gtk4DbDatasheet ):

    def __init__( self , read_only=False , auto_apply=False , **kwargs ):
        super( Gtk4OracleDatasheet , self ).__init__( read_only=read_only , auto_apply=auto_apply , **kwargs )


##############################################################################################################
# Form flavours

class Gtk4PostgresForm( Gtk4PostgresAbstract , Gtk4DbForm ):

    def __init__( self , read_only=False , auto_apply=False , **kwargs ):
        super( Gtk4PostgresForm , self ).__init__( read_only=read_only , auto_apply=auto_apply , **kwargs )

class Gtk4MySQLForm( Gtk4MySQLAbstract , Gtk4DbForm  ):

    def __init__( self , read_only=False , auto_apply=False , **kwargs ):
        super( Gtk4MySQLForm , self ).__init__( read_only=read_only , auto_apply=auto_apply , **kwargs )


class Gtk4SQLiteForm( Gtk4SQLiteAbstract , Gtk4DbForm  ):

    def __init__( self , read_only=False , auto_apply=False , **kwargs ):
        super( Gtk4SQLiteForm , self ).__init__( read_only=read_only , auto_apply=auto_apply , **kwargs )

class Gtk4OracleForm( Gtk4OracleAbstract , Gtk4DbForm  ):

    def __init__( self , read_only=False , auto_apply=False , **kwargs ):
        super( Gtk4OracleForm , self ).__init__( read_only=read_only , auto_apply=auto_apply , **kwargs )

