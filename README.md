![gtk4-db-binder collage](/gtk4-db-binder-photocollage.png?raw=true "gtk4-db-binder screenshot collage")

gtk4-db-binder generates 'form' and 'datasheet' objects that bind
a table in a relational database to widgets in a gtk4 application.

Current functionality includes:

* Detection of primary keys
* Generating SQL for insert, update, delete statements
* Handling auto-incrementing primary keys
* Generating a 'recordset toolbar' with buttons for insert, undo, delete, apply operations ( both form and datasheet )
* Support for multiple database backends ( postgres, mysql, sqlite, oracle - partial ), with more simple to add
* Binding multiple gtk4-db-binder objects together in a parent/child relationship, so the child gets requeried when the parent IDs update, and foreign keys are automatically set when inserting into the child
* DropDrop support in both form and datasheet

For datasheets, you supply a gtk box, and the datasheet ( and recordset toolbox ) is created inside it.

For forms, you supply a gtk builder object, and columns are bound to identically-named gtk4 widgets.

Most of the testing so far as been against SQLite ( the example app uses SQLite ) and Postgres. While I won't guarantee there are no bugs, the scope for "catastrophic" errors like accidentally updating an entire table are very slim.

The project is in active development, and I plan to keep it that way. I will host a bunch of data-centric desktop applications ( I'm a software + data engineer ) on top of this library going forwards. My other main project at this point is porting my ETL framework from perl-gtk3 to python-gtk4. This will drive ongoing development and testing of gtk4-db-binder.
