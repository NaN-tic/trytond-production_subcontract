.. inheritref:: production_subcontract/production:section:subcontract

----------------
Subcontractación
----------------

En la producción, disponemos del campo "Producto subcontractado" que nos permite
generar solicitudes de compra. Para generar las solicitudes de compra, dispondremos
de un nuevo botón "Crea solicitudes de compra" que nos creará una solicitud de compra.

En la pestaña "Información adicional" de la producción podremos ir a la solictud de
compra que hemos generado con la opcipn "Crea solicitudes de compra".

Una vez la solicitud la hemos convertido a compra y esta compra la hemos realizado,
nos generará un albarán interno. En este momento, los campo "Almacén" y "Almacén destinación"
de la producción, se nos recalculará con los nuevos datos:

- Almacén: El almacén de nuestro proveedor (definido en el tercero, "Almacén producción")
- Almacén destinación: El almacén que hemos seleccionado al inicio de crear la producción.

Una vez hemos realizado la compra y nos haya recalculado los campos "Almacén" y
"Almacén destinación" podremos crear albaranes internos para la entrega de materiales
para la realización de la producción.

Para generar albaranes internos disponemos del botón "Crear albarán interno" en
la vista formulario de la producción o bien mediante la acción "Crear albaranes internos"
si deseamos seleccionar varias producciones.

En el caso que la producción ya se disponga de albaranes internos, y se desea crear
nuevos albaranes, nos alertará de su existencia y el usuario podrá confirmar o cancelar
la operación.
