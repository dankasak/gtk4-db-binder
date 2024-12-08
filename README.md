![gtk4-db-binder collage](/gtk4-db-binder-photocollage.png?raw=true "gtk4-db-binder screenshot collage")

gtk4-db-binder generates 'form' and 'datasheet' objects that bind
a table in a relational database to widgets in a gtk4 application.

Current functionality includes:

* Generating SQL for insert, update, delete statements
* Generating a 'recordset toolbar' with buttons for insert, undo, delete, apply operations
* Support for multiple database backends ( postgres, mysql, sqlite, oracle - partial )
* Fetching auto-incrementing IDs upon insert, and registering in the model
* Binding multiple gtk4-db-binder objects together in a parent/child relationship, so the child gets requeried when the parent IDs update, and foreign keys are automatically set when inserting into the child

For datasheets, you supply a gtk box, and the datasheet ( and recordset toolbox ) is created inside it.

For forms, you supply a gtk builder object, and columns are bound to identically-named gtk4 widgets.
