# DataMolder: Sistema de Gestión de Registros de Datos de Alto Rendimiento

DataMolder es una librería de Python diseñada para proporcionar una manera flexible y eficiente de gestionar colecciones de registros de datos. Ofrece seguridad de tipo, validación de datos y operaciones funcionales, haciéndola ideal para tareas de manipulación y análisis de datos en entornos de desarrollo y ciencia de datos.

## 1. Visión General

DataMolder busca simplificar la gestión de datos tabulares, similar a un DataFrame, pero con un enfoque más estricto en la tipificación, la validación y la inmutabilidad controlada. Combina la definición de un esquema (`Header`) con la gestión de los datos reales (`Data`), todo encapsulado en la clase `DataMolder` para una experiencia de usuario unificada.

## 2. Instalación

Dado que `DataMolder.py` es un archivo local, la instalación consiste en incluir el archivo en tu proyecto.

Para usar DataMolder, simplemente incluye el archivo `DataMolder.py` en tu proyecto de Python.

```python
# data_processing_script.py
from DataMolder import DataMolder, ValidationError, ColumnNotFoundError, TypeValidationError, ConstraintValidationError

# Tu código aquí
```

## 3. Conceptos Clave

### 3.1. Header (Encabezado)

La clase `Header` se encarga de gestionar las definiciones de las columnas, la información de tipo, los valores por defecto, si una columna es requerida y si es una clave.

- **Definición de Columnas**: Permite definir columnas con nombre, tipo (`Type`), valor por defecto (`Any`), si es un campo requerido (`bool`) y si es un campo clave (`bool`).
- **Validadores Personalizados**: Soporta la adición de funciones de validación personalizadas por columna.
- **Control de Nulos y Tipos**: Permite configurar si se permiten valores `None` y si se aplica una verificación de tipos estricta.

### 3.2. Data (Datos)

La clase `Data` gestiona la colección de registros de datos basándose en el `Header` proporcionado. Proporciona una interfaz mutable para almacenar y manipular los datos, manteniendo la seguridad de tipo y las reglas de validación.

- **Almacenamiento**: Almacena las filas internamente como listas de valores para un acceso eficiente.
- **Validación en Cambios**: Puede configurarse para validar los datos en cada modificación.
- **Control de Modificaciones**: Rastrea qué filas han sido modificadas.
- **Navegación**: Incluye un cursor interno para moverse entre filas y la capacidad de establecer marcadores.
- **Bloqueo**: Permite bloquear filas y columnas individuales, o todas las filas/columnas, para prevenir modificaciones no deseadas.

### 3.3. DataMolder (Moldeador de Datos)

La clase `DataMolder` es el contenedor principal que combina la gestión del `Header` y la `Data`. Ofrece una solución completa para el manejo de datos con seguridad de tipo, estructuras de datos mutables y validación exhaustiva.

- **Inicialización Simplificada**: Permite definir las columnas y sus propiedades directamente al inicializar la instancia de `DataMolder`.
- **Métodos Convenientes**: Expone métodos para añadir, actualizar, eliminar, mover, filtrar, mapear y analizar datos, delegando a las clases `Header` y `Data`.

### 3.4. Validación y Errores

DataMolder aplica una validación rigurosa a los datos para mantener su integridad. Define varias excepciones personalizadas:

- **`ValidationError`**: Excepción base para errores de validación.
- **`TypeValidationError`**: Lanzada cuando la validación de tipo falla.
- **`ConstraintValidationError`**: Lanzada cuando falla una validación de restricción personalizada.
- **`ColumnNotFoundError`**: Lanzada cuando no se encuentra una columna.
- **`PermissionError`**: Lanzada al intentar modificar una fila o columna bloqueada.
- **`IndexError`**: Lanzada al acceder a índices de fila inválidos.
- **`ValueError`**: Lanzada por diversas razones, como nombres de columna no únicos, valores por defecto inválidos, campos requeridos faltantes o valores de clave duplicados.

## 4. Uso Básico

### 4.1. Creación de una Instancia de DataMolder

Se define el esquema de las columnas al inicializar `DataMolder`. Puedes especificar el nombre de la columna, el tipo de dato, un valor por defecto, si es requerida y si es un campo clave.

```python
from DataMolder import DataMolder, TypeValidationError, ColumnNotFoundError

# Ejemplo de definición de columnas: (nombre, tipo, valor_por_defecto, es_requerido, es_clave)
dm = DataMolder([
    ('id', int, None, True, True),          # Campo clave requerido
    ('name', str, "N/A", True, False),      # Campo requerido con valor por defecto
    ('age', int, 0, False, False),          # Campo opcional con valor por defecto
    ('email', str, None, False, False)      # Campo opcional sin valor por defecto
])

print(f"Columnas definidas: {dm.header.columns}")
# Salida: Columnas definidas: ['id', 'name', 'age', 'email']
```

### 4.2. Añadir Filas

Puedes añadir filas usando una lista de valores (ordenados según la definición de columnas) o un diccionario de clave=valor. DataMolder aplica validaciones en este paso.

```python
# Añadir una fila usando una lista (debe coincidir con el orden de las columnas)
dm.add_row([1, "Alice", 30, "alice@example.com"])
print(f"Fila 0: {dm.get_row(0)}")
# Salida: Fila 0: {'id': 1, 'name': 'Alice', 'age': 30, 'email': 'alice@example.com'}

# Añadir una fila usando un diccionario (se aplicarán los valores por defecto para los campos no especificados)
dm.add_row(id=2, name="Bob", age=24)
print(f"Fila 1: {dm.get_row(1)}")
# Salida: Fila 1: {'id': 2, 'name': 'Bob', 'age': 24, 'email': None}

try:
    # Intentar añadir una fila con un ID duplicado (fallará por ser campo clave único)
    dm.add_row(id=1, name="Charlie")
except ValueError as e:
    print(f"Error al añadir fila: {e}")
    # Salida: Error al añadir fila: Key field values {'id': 1} already exist in another row. Key fields: ['id']

try:
    # Intentar añadir una fila con tipo incorrecto
    dm.add_row(id=3, name="David", age="veinte")
except TypeValidationError as e:
    print(f"Error de validación de tipo: {e}")
    # Salida: Error de validación de tipo: Type mismatch for age: expected int, got str

try:
    # Intentar añadir una fila sin un campo requerido
    dm.add_row(id=4, age=25)
except ValueError as e:
    print(f"Error de campo requerido: {e}")
    # Salida: Error de campo requerido: Required field 'name' is missing or None
```

### 4.3. Obtener Filas y Columnas

Puedes obtener filas por índice o todas las filas de una columna específica.

```python
# Obtener una fila por índice
row_data = dm.get_row(0)
print(f"Datos de la fila 0: {row_data}")
# Salida: Datos de la fila 0: {'id': 1, 'name': 'Alice', 'age': 30, 'email': 'alice@example.com'}

# Obtener una columna completa
ages = dm.get_column('age')
print(f"Edades: {ages}")
# Salida: Edades: [30, 24]

# Iterar sobre las filas
print("Todas las filas:")
for row in dm:
    print(row)
# Salida:
# Todas las filas:
# {'id': 1, 'name': 'Alice', 'age': 30, 'email': 'alice@example.com'}
# {'id': 2, 'name': 'Bob', 'age': 24, 'email': None}
```

### 4.4. Actualizar Valores

Los valores se pueden actualizar por índice de fila y nombre de columna. La validación se aplica automáticamente si `validate_on_change` es `True` (por defecto).

```python
dm.update_value(0, 'age', 31)
print(f"Edad de Alice actualizada: {dm.get_row(0)['age']}")
# Salida: Edad de Alice actualizada: 31

try:
    # Intentar actualizar con un tipo incorrecto
    dm.update_value(0, 'age', "treinta")
except TypeValidationError as e:
    print(f"Error al actualizar: {e}")
    # Salida: Error al actualizar: Type mismatch for age: expected int, got str

try:
    # Intentar actualizar una columna inexistente
    dm.update_value(0, 'city', "Madrid")
except ColumnNotFoundError as e:
    print(f"Error al actualizar: {e}")
    # Salida: Error al actualizar: Columna 'city' no encontrada
```

### 4.5. Eliminar Filas

Las filas pueden eliminarse por su índice.

```python
print(f"Filas antes de eliminar: {len(dm)}") # Salida: Filas antes de eliminar: 2
dm.remove_row(0)
print(f"Filas después de eliminar: {len(dm)}") # Salida: Filas después de eliminar: 1
print(f"Nueva fila 0: {dm.get_row(0)}") # Salida: Nueva fila 0: {'id': 2, 'name': 'Bob', 'age': 24, 'email': None}
```

## 5. Funcionalidades Avanzadas

### 5.1. Gestión de Columnas

Las columnas pueden ser añadidas o eliminadas del esquema.

```python
dm.header.add_column('status', str, validator=lambda x: x in ['active', 'inactive'])
print(f"Columnas después de añadir: {dm.header.columns}")
# Salida: Columnas después de añadir: ['id', 'name', 'age', 'email', 'status']

dm.update_value(0, 'status', 'active')
print(f"Fila 0 con status: {dm.get_row(0)}")
# Salida: Fila 0 con status: {'id': 2, 'name': 'Bob', 'age': 24, 'email': None, 'status': 'active'}

try:
    dm.update_value(0, 'status', 'pending')
except ConstraintValidationError as e:
    print(f"Error de validación de restricción: {e}")
    # Salida: Error de validación de restricción: Validation failed for status with value: pending

dm.header.remove_column('email')
print(f"Columnas después de eliminar: {dm.header.columns}")
# Salida: Columnas después de eliminar: ['id', 'name', 'age', 'status']
# Nota: La eliminación de columnas del header afecta la representación de las filas existentes.
# Las filas internas almacenan los datos por índice, por lo que la eliminación de una columna afecta los índices subsiguientes.
# Para escenarios complejos de manipulación de columnas, considera `slice` o `get_columns`.
```

### 5.2. Operaciones de Cursor y Marcadores (Bookmarks)

DataMolder incluye un cursor para navegar por las filas y la capacidad de establecer marcadores para posiciones específicas.

```python
dm_cursor = DataMolder([('item', str)])
dm_cursor.add_row(item="Apple")
dm_cursor.add_row(item="Banana")
dm_cursor.add_row(item="Cherry")

print(f"Posición inicial del cursor: {dm_cursor.current_row}") # Salida: Posición inicial del cursor: None

dm_cursor.move_next()
print(f"Fila actual (move_next): {dm_cursor.current_row}") # Salida: Fila actual (move_next): {'item': 'Apple', '_modified': False}

dm_cursor.add_bookmark("first_item")
print(f"Marcadores: {dm_cursor.list_bookmarks()}") # Salida: Marcadores: {'first_item': 0}

dm_cursor.move_next()
print(f"Fila actual (move_next): {dm_cursor.current_row}") # Salida: Fila actual (move_next): {'item': 'Banana', '_modified': False}

dm_cursor.goto_bookmark("first_item")
print(f"Fila actual (goto_bookmark): {dm_cursor.current_row}") # Salida: Fila actual (goto_bookmark): {'item': 'Apple', '_modified': False}

dm_cursor.remove_bookmark("first_item")
print(f"Marcadores después de eliminar: {dm_cursor.list_bookmarks()}") # Salida: Marcadores después de eliminar: {}
```

### 5.3. Bloqueo de Filas/Columnas

Puedes bloquear filas o columnas para prevenir modificaciones, lo cual es útil para asegurar la inmutabilidad de ciertas partes de los datos.

```python
dm_lock = DataMolder([('id', int), ('value', int)])
dm_lock.add_row(id=1, value=100)
dm_lock.add_row(id=2, value=200)

print(f"Fila 0 bloqueada: {dm_lock.is_row_locked(0)}") # Salida: Fila 0 bloqueada: False
dm_lock.lock_row(0)
print(f"Fila 0 bloqueada: {dm_lock.is_row_locked(0)}") # Salida: Fila 0 bloqueada: True

try:
    dm_lock.update_value(0, 'value', 150)
except PermissionError as e:
    print(f"Error de permiso al actualizar fila: {e}")
    # Salida: Error de permiso al actualizar fila: Row 0 is locked and cannot be modified

dm_lock.lock_column('id')
print(f"Columna 'id' bloqueada: {dm_lock.is_column_locked('id')}") # Salida: Columna 'id' bloqueada: True

try:
    dm_lock.update_value(1, 'id', 3)
except PermissionError as e:
    print(f"Error de permiso al actualizar columna: {e}")
    # Salida: Error de permiso al actualizar columna: Column 'id' is locked and cannot be modified

dm_lock.lock_all_rows()
print(f"Todas las filas bloqueadas: {dm_lock.is_row_locked(1)}") # Salida: Todas las filas bloqueadas: True
dm_lock.unlock_all_rows()
print(f"Todas las filas bloqueadas: {dm_lock.is_row_locked(1)}") # Salida: Todas las filas bloqueadas: False
```

### 5.4. Transformación y Filtrado de Datos

DataMolder proporciona métodos funcionales para transformar y filtrar los datos, similares a las operaciones de un DataFrame.

#### 5.4.1. `filter(predicate: Callable[[Dict[str, Any]], bool]) -> 'DataMolder'`

Crea una nueva instancia de `DataMolder` con las filas que cumplen una condición especificada por una función `predicate`.

```python
dm_transform = DataMolder([('id', int), ('name', str), ('age', int)])
dm_transform.add_row(id=1, name="Alice", age=30)
dm_transform.add_row(id=2, name="Bob", age=25)
dm_transform.add_row(id=3, name="Charlie", age=35)

filtered_data = dm_transform.filter(lambda row: row['age'] > 28)
print("Datos filtrados (edad > 28):")
for row in filtered_data:
    print(row)
# Salida:
# Datos filtrados (edad > 28):
# {'id': 1, 'name': 'Alice', 'age': 30, '_modified': False}
# {'id': 3, 'name': 'Charlie', 'age': 35, '_modified': False}
```

#### 5.4.2. `map(transform: Callable[[Dict[str, Any]], Dict[str, Any]]) -> 'DataMolder'`

Aplica una función de transformación a cada fila, devolviendo una nueva instancia rules de `DataMolder` con las filas transformadas. Esto puede cambiar la estructura de las columnas si la función `transform` lo hace.

```python
mapped_data = dm_transform.map(lambda row: {'id_str': str(row['id']), 'name_upper': row['name'].upper()})
print("Datos mapeados:")
print(f"Nuevas columnas: {mapped_data.header.columns}")
# Salida: Nuevas columnas: ['id_str', 'name_upper']
for row in mapped_data:
    print(row)
# Salida:
# Datos mapeados:
# {'id_str': '1', 'name_upper': 'ALICE', '_modified': False}
# {'id_str': '2', 'name_upper': 'BOB', '_modified': False}
# {'id_str': '3', 'name_upper': 'CHARLIE', '_modified': False}
```

#### 5.4.3. `sort(column: str, reverse: bool = False) -> None`

Ordena las filas en su lugar por el valor de una columna específica.

```python
print("Datos antes de ordenar:")
for row in dm_transform:
    print(row)
# Salida:
# Datos antes de ordenar:
# {'id': 1, 'name': 'Alice', 'age': 30, '_modified': False}
# {'id': 2, 'name': 'Bob', 'age': 25, '_modified': False}
# {'id': 3, 'name': 'Charlie', 'age': 35, '_modified': False}

dm_transform.sort('age')
print("Datos ordenados por edad (ascendente):")
for row in dm_transform:
    print(row)
# Salida:
# Datos ordenados por edad (ascendente):
# {'id': 2, 'name': 'Bob', 'age': 25, '_modified': False}
# {'id': 1, 'name': 'Alice', 'age': 30, '_modified': False}
# {'id': 3, 'name': 'Charlie', 'age': 35, '_modified': False}

dm_transform.sort('name', reverse=True)
print("Datos ordenados por nombre (descendente):")
for row in dm_transform:
    print(row)
# Salida:
# Datos ordenados por nombre (descendente):
# {'id': 2, 'name': 'Bob', 'age': 25, '_modified': False}
# {'id': 3, 'name': 'Charlie', 'age': 35, '_modified': False}
# {'id': 1, 'name': 'Alice', 'age': 30, '_modified': False}
```

#### 5.4.4. `pivot(row_column: str, column_values: str, value_column: str) -> 'DataMolder'`

Crea una tabla pivote transformando los valores únicos de una columna en nuevas columnas.

```python
dm_pivot = DataMolder([('date', str), ('metric', str), ('value', int)])
dm_pivot.add_row(date="2023-01", metric="sales", value=100)
dm_pivot.add_row(date="2023-01", metric="costs", value=80)
dm_pivot.add_row(date="2023-02", metric="sales", value=120)
dm_pivot.add_row(date="2023-02", metric="costs", value=90)
dm_pivot.add_row(date="2023-02", metric="profit", value=30) # Añadimos una nueva métrica

print("Datos originales para pivotar:")
for row in dm_pivot:
    print(row)
# Salida:
# Datos originales para pivotar:
# {'date': '2023-01', 'metric': 'sales', 'value': 100, '_modified': False}
# {'date': '2023-01', 'metric': 'costs', 'value': 80, '_modified': False}
# {'date': '2023-02', 'metric': 'sales', 'value': 120, '_modified': False}
# {'date': '2023-02', 'metric': 'costs', 'value': 90, '_modified': False}
# {'date': '2023-02', 'metric': 'profit', 'value': 30, '_modified': False}

pivoted_data = dm_pivot.pivot('date', 'metric', 'value')
print("\nDatos pivotados:")
print(f"Columnas pivotadas: {pivoted_data.header.columns}")
# Salida: Columnas pivotadas: ['date', 'costs', 'profit', 'sales']
for row in pivoted_data:
    print(row)
# Salida:
# Datos pivotados:
# {'date': '2023-01', 'costs': 80, 'profit': None, 'sales': 100, '_modified': False}
# {'date': '2023-02', 'costs': 90, 'profit': 30, 'sales': 120, '_modified': False}
```

#### 5.4.5. `unpivot(id_columns: List[str], value_name: str = 'value', variable_name: str = 'variable') -> 'DataMolder'`

Transforma columnas en filas, invirtiendo la operación de pivote.

```python
unpivoted_data = pivoted_data.unpivot(['date'])
print("\nDatos despivotados:")
print(f"Columnas despivotadas: {unpivoted_data.header.columns}")
# Salida: Columnas despivotadas: ['date', 'variable', 'value']
for row in unpivoted_data:
    print(row)
# Salida:
# Datos despivotados:
# {'date': '2023-01', 'variable': 'costs', 'value': 80, '_modified': False}
# {'date': '2023-01', 'variable': 'profit', 'value': None, '_modified': False}
# {'date': '2023-01', 'variable': 'sales', 'value': 100, '_modified': False}
# {'date': '2023-02', 'variable': 'costs', 'value': 90, '_modified': False}
# {'date': '2023-02', 'variable': 'profit', 'value': 30, '_modified': False}
# {'date': '2023-02', 'variable': 'sales', 'value': 120, '_modified': False}
```

### 5.5. Manipulación de Estructura

DataMolder permite reordenar y seleccionar subconjuntos de filas y columnas.

#### 5.5.1. `move_row_to(from_index: int, to_index: int) -> bool`

Mueve una fila de una posición a otra.

#### 5.5.2. `move_row_by(index: int, offset: int) -> bool`

Mueve una fila por un número relativo de posiciones.

#### 5.5.3. `move_column_to(column: str, new_index: int) -> bool`

Mueve una columna a una posición específica.

#### 5.5.4. `move_column_by(column: str, offset: int) -> bool`

Mueve una columna por un número relativo de posiciones.

```python
dm_move = DataMolder([('a', int), ('b', int), ('c', int)])
dm_move.add_row(a=1, b=2, c=3)
dm_move.add_row(a=4, b=5, c=6)
dm_move.add_row(a=7, b=8, c=9)

print("Original:")
for row in dm_move: print(row)
# Salida:
# Original:
# {'a': 1, 'b': 2, 'c': 3, '_modified': False}
# {'a': 4, 'b': 5, 'c': 6, '_modified': False}
# {'a': 7, 'b': 8, 'c': 9, '_modified': False}

dm_move.move_row_to(0, 2) # Mueve la primera fila a la última posición
print("\nDespués de move_row_to(0, 2):")
for row in dm_move: print(row)
# Salida:
# Después de move_row_to(0, 2):
# {'a': 4, 'b': 5, 'c': 6, '_modified': False}
# {'a': 7, 'b': 8, 'c': 9, '_modified': False}
# {'a': 1, 'b': 2, 'c': 3, '_modified': False}

dm_move.move_column_by('c', -2) # Mueve la columna 'c' dos posiciones a la izquierda
print(f"\nColumnas después de move_column_by('c', -2): {dm_move.header.columns}")
# Salida: Columnas después de move_column_by('c', -2): ['c', 'a', 'b']
for row in dm_move: print(row)
# Salida:
# {'c': 6, 'a': 4, 'b': 5, '_modified': False}
# {'c': 9, 'a': 7, 'b': 8, '_modified': False}
# {'c': 3, 'a': 1, 'b': 2, '_modified': False}
```

#### 5.5.5. `swap_rows(i: int, j: int) -> bool`

Intercambia dos filas basándose en sus índices.

#### 5.5.6. `swap_row_range(start1: int, end1: int, start2: int, end2: int) -> bool`

Intercambia dos rangos de filas.

#### 5.5.7. `swap_columns(i: str, j: str) -> bool`

Intercambia dos columnas basándose en sus nombres.

#### 5.5.8. `swap_column_range(start1: str, end1: str, start2: str, end2: str) -> bool`

Intercambia dos rangos de columnas.

```python
dm_swap = DataMolder([('col1', int), ('col2', str), ('col3', float)])
dm_swap.add_row(col1=1, col2="A", col3=1.1)
dm_swap.add_row(col1=2, col2="B", col3=2.2)
dm_swap.add_row(col1=3, col2="C", col3=3.3)

print("\nOriginal para swap:")
for row in dm_swap: print(row)
# Salida:
# Original para swap:
# {'col1': 1, 'col2': 'A', 'col3': 1.1, '_modified': False}
# {'col1': 2, 'col2': 'B', 'col3': 2.2, '_modified': False}
# {'col1': 3, 'col2': 'C', 'col3': 3.3, '_modified': False}

dm_swap.swap_rows(0, 2)
print("\nDespués de swap_rows(0, 2):")
for row in dm_swap: print(row)
# Salida:
# Después de swap_rows(0, 2):
# {'col1': 3, 'col2': 'C', 'col3': 3.3, '_modified': False}
# {'col1': 2, 'col2': 'B', 'col3': 2.2, '_modified': False}
# {'col1': 1, 'col2': 'A', 'col3': 1.1, '_modified': False}

dm_swap.swap_columns('col1', 'col3')
print(f"\nColumnas después de swap_columns('col1', 'col3'): {dm_swap.header.columns}")
# Salida: Columnas después de swap_columns('col1', 'col3'): ['col3', 'col2', 'col1']
for row in dm_swap: print(row)
# Salida:
# {'col3': 3.3, 'col2': 'C', 'col1': 3, '_modified': False}
# {'col3': 2.2, 'col2': 'B', 'col1': 2, '_modified': False}
# {'col3': 1.1, 'col2': 'A', 'col1': 1, '_modified': False}
```

#### 5.5.9. `slice(row_slice: Optional[slice] = None, columns: Optional[List[str]] = None) -> 'DataMolder'`

Obtiene un subconjunto de los datos seleccionando filas y/o columnas.

#### 5.5.10. `get_columns(columns: List[str]) -> 'DataMolder'`

Un método de conveniencia para seleccionar un subconjunto de columnas.

#### 5.5.11. `head(n: int = 5) -> 'DataMolder'`

Obtiene las primeras `n` filas de los datos.

#### 5.5.12. `tail(n: int = 5) -> 'DataMolder'`

Obtiene las últimas `n` filas de los datos.

```python
dm_slice = DataMolder([('id', int), ('name', str), ('age', int), ('city', str)])
dm_slice.add_row(id=1, name="Alice", age=30, city="NY")
dm_slice.add_row(id=2, name="Bob", age=25, city="LA")
dm_slice.add_row(id=3, name="Charlie", age=35, city="NY")
dm_slice.add_row(id=4, name="David", age=40, city="LA")
dm_slice.add_row(id=5, name="Eve", age=22, city="Chicago")

# Obtener filas 1 a 3 (índices 1 y 2) y columnas 'name', 'age'
subset = dm_slice.slice(slice(1, 3), ['name', 'age'])
print("\nSlice (filas 1-2, columnas 'name', 'age'):")
for row in subset: print(row)
# Salida:
# Slice (filas 1-2, columnas 'name', 'age'):
# {'name': 'Bob', 'age': 25, '_modified': False}
# {'name': 'Charlie', 'age': 35, '_modified': False}

# Obtener solo las columnas 'id' y 'city'
id_city_data = dm_slice.get_columns(['id', 'city'])
print("\nColumnas 'id' y 'city':")
for row in id_city_data: print(row)
# Salida:
# Columnas 'id' y 'city':
# {'id': 1, 'city': 'NY', '_modified': False}
# {'id': 2, 'city': 'LA', '_modified': False}
# {'id': 3, 'city': 'NY', '_modified': False}
# {'id': 4, 'city': 'LA', '_modified': False}
# {'id': 5, 'city': 'Chicago', '_modified': False}

first_two = dm_slice.head(2)
print("\nPrimeras 2 filas (head):")
for row in first_two: print(row)
# Salida:
# Primeras 2 filas (head):
# {'id': 1, 'name': 'Alice', 'age': 30, 'city': 'NY', '_modified': False}
# {'id': 2, 'name': 'Bob', 'age': 25, 'city': 'LA', '_modified': False}
```

#### 5.5.13. `concatenate(other: 'Data', validate_structure: bool = True) -> 'DataMolder'`

Concatena dos instancias de `DataMolder` apilando las filas. Requiere que las estructuras sean compatibles.

#### 5.5.14. `concat_columns(other: 'Data', validate_rows: bool = True) -> 'DataMolder'`

Concatena dos instancias de `DataMolder` apilando las columnas. Requiere que no haya columnas duplicadas y, opcionalmente, el mismo número de filas.

```python
dm_concat1 = DataMolder([('id', int), ('item', str)])
dm_concat1.add_row(id=1, item="Apple")
dm_concat1.add_row(id=2, item="Banana")

dm_concat2 = DataMolder([('id', int), ('item', str)])
dm_concat2.add_row(id=3, item="Cherry")
dm_concat2.add_row(id=4, item="Date")

combined_rows = dm_concat1.concatenate(dm_concat2)
print("\nConcatenación de filas:")
for row in combined_rows: print(row)
# Salida:
# Concatenación de filas:
# {'id': 1, 'item': 'Apple', '_modified': False}
# {'id': 2, 'item': 'Banana', '_modified': False}
# {'id': 3, 'item': 'Cherry', '_modified': False}
# {'id': 4, 'item': 'Date', '_modified': False}

dm_cols1 = DataMolder([('id', int), ('name', str)])
dm_cols1.add_row(id=1, name="Alice")
dm_cols1.add_row(id=2, name="Bob")

dm_cols2 = DataMolder([('age', int), ('city', str)])
dm_cols2.add_row(age=30, city="NY")
dm_cols2.add_row(age=25, city="LA")

combined_cols = dm_cols1.concat_columns(dm_cols2)
print("\nConcatenación de columnas:")
print(f"Columnas resultantes: {combined_cols.header.columns}")
# Salida: Columnas resultantes: ['id', 'name', 'age', 'city']
for row in combined_cols: print(row)
# Salida:
# {'id': 1, 'name': 'Alice', 'age': 30, 'city': 'NY', '_modified': False}
# {'id': 2, 'name': 'Bob', 'age': 25, 'city': 'LA', '_modified': False}
```

### 5.6. Análisis de Datos

DataMolder incluye métodos para obtener métricas y estadísticas descriptivas de los datos.

#### 5.6.1. `get_size_metrics() -> Dict[str, Any]`

Devuelve métricas sobre el tamaño y el uso de memoria de los datos.

```python
metrics = dm_slice.get_size_metrics()
print(f"\nMétricas de tamaño: {metrics}")
# Salida: Métricas de tamaño: {'row_count': 5, 'column_count': 4, 'total_cells': 20, 'modified_rows': 0, 'approx_memory_bytes': ...}
```

#### 5.6.2. `get_distinct_values(column: str) -> Dict[Any, int]`

Obtiene el recuento de valores distintos en una columna.

```python
city_counts = dm_slice.get_distinct_values('city')
print(f"Recuento de ciudades: {city_counts}")
# Salida: Recuento de ciudades: {'NY': 2, 'LA': 2, 'Chicago': 1}
```

#### 5.6.3. `get_column_stats(column: str) -> Dict[str, Any]`

Obtiene información estadística sobre una columna (recuentos, nulos, min/max, promedio, etc., según el tipo de columna).

```python
age_stats = dm_slice.get_column_stats('age')
print(f"Estadísticas de edad: {age_stats}")
# Salida: Estadísticas de edad: {'count': 5, 'null_count': 0, 'distinct_count': 5, 'min': 22, 'max': 40, 'sum': 152, 'avg': 30.4}

name_stats = dm_slice.get_column_stats('name')
print(f"Estadísticas de nombre: {name_stats}")
# Salida: Estadísticas de nombre: {'count': 5, 'null_count': 0, 'distinct_count': 5, 'min_length': 3, 'max_length': 7, 'avg_length': 5.2}
```

### 5.7. Comparación de Datos

#### 5.7.1. `compare(other: 'Data', key_columns: List[str], ignore_columns: List[str] = None) -> Dict[str, Any]`

Compara dos instancias de `DataMolder` y devuelve sus diferencias, incluyendo diferencias de estructura, filas faltantes, filas extra y filas modificadas.

```python
dm_comp1 = DataMolder([('id', int), ('name', str), ('value', int), ('status', str)])
dm_comp1.add_row(id=1, name="Item A", value=100, status="active")
dm_comp1.add_row(id=2, name="Item B", value=200, status="active")
dm_comp1.add_row(id=3, name="Item C", value=300, status="inactive")

dm_comp2 = DataMolder([('id', int), ('name', str), ('value', float), ('new_col', bool)]) # 'value' con tipo diferente, 'new_col' extra
dm_comp2.add_row(id=1, name="Item A", value=105.0, new_col=True) # Fila modificada (value)
dm_comp2.add_row(id=2, name="Item B", value=200.0, new_col=False) # Fila sin cambios (respecto a campos comunes)
dm_comp2.add_row(id=4, name="Item D", value=400.0, new_col=True) # Fila extra

diff = dm_comp1.compare(dm_comp2, ['id'], ignore_columns=['status', 'new_col'])

print("\nResultados de la comparación:")
print(f"Diferencias de estructura: {diff['structure_diff']}")
# Salida: Diferencias de estructura: {'missing_columns': [], 'extra_columns': [], 'type_mismatches': [{'column': 'value', 'self_type': 'int', 'other_type': 'float'}]}
print(f"Filas faltantes en el segundo DataMolder: {diff['missing_rows']}")
# Salida: Filas faltantes en el segundo DataMolder: [{'id': 3}]
print(f"Filas extra en el segundo DataMolder: {diff['extra_rows']}")
# Salida: Filas extra en el segundo DataMolder: [{'id': 4}]
print(f"Filas modificadas: {diff['modified_rows']}")
# Salida: Filas modificadas: [{'key': {'id': 1}, 'changes': {'value': {'old': 100, 'new': 105.0}}}]
print(f"Total de diferencias: {diff['total_differences']}")
# Salida: Total de diferencias: 3 (1 type mismatch + 1 missing row + 1 extra row + 1 modified row)
```

## 6. Manejo de Errores y Excepciones

DataMolder utiliza un sistema de excepciones claro para informar sobre problemas de validación y operación. Es crucial capturar estas excepciones en tu código para manejar escenarios inesperados.

- **`ValidationError`**: Captura errores generales de validación.
- **`TypeValidationError`**: Errores de tipo de datos.
- **`ConstraintValidationError`**: Errores de validadores personalizados.
- **`ColumnNotFoundError`**: Acceso a columnas inexistentes.
- **`IndexError`**: Índices de fila fuera de rango.
- **`PermissionError`**: Intentos de modificación en filas/columnas bloqueadas.
- **`ValueError`**: Variedad de errores lógicos como duplicados, incompatibilidades de esquema, etc.

## 7. Referencia de la API

### Clases Principales

#### `class DataMolder`

```python
class DataMolder:
    def __init__(
        self,
        columns: List[Union[str, tuple[str, Type, Any, bool, bool]]], # (name, type, default, required, key)
        validators: Optional[Dict[str, Callable[[Any], bool]]] = None,
        allow_none: bool = True,
        type_checking: bool = True,
        validate_on_change: bool = True
    ):
        """
        Inicializa DataMolder.
        
        Args:
            columns: Lista de definiciones de columna:
                - str: Solo nombre de columna
                - (name, type): Columna con tipo
                - (name, type, default): Con valor por defecto
                - (name, type, default, required, key): Definición completa
            validators: Funciones de validación opcionales.
            allow_none: Si se permiten valores None.
            type_checking: Si se aplica una verificación de tipo estricta.
            validate_on_change: Si se valida en cada cambio de datos.
        """
        # ...
```

#### Atributos

- **`header`**: Instancia de `Header` que define la estructura de las columnas.
- **`data`**: Instancia de `Data` que gestiona las filas de datos.

#### Métodos

- **`add_bookmark(name: str) -> bool`**: Añade un marcador en la posición actual del cursor.
- **`goto_bookmark(name: str) -> bool`**: Mueve el cursor a la posición del marcador.
- **`remove_bookmark(name: str) -> bool`**: Elimina un marcador.
- **`list_bookmarks() -> Dict[str, int]`**: Devuelve un diccionario de todos los marcadores.
- **`is_key_field(column: str) -> bool`**: Comprueba si una columna es un campo clave.
- **`key_fields` (property) -> `List[str]`**: Lista de nombres de columnas que son campos clave.
- **`validate_key_uniqueness(values: Dict[str, Any]) -> bool`**: Valida que los valores de los campos clave sean únicos.
- **`add_row(values: Union[List[Any], Dict[str, Any]]) -> bool`**: Añade una nueva fila. Soporta listas o diccionarios.
- **`get_row(index: int) -> Optional[Dict[str, Any]]`**: Obtiene una fila por índice como un diccionario.
- **`get_column(name: str) -> Optional[List[Any]]`**: Obtiene todos los valores de una columna.
- **`update_value(row: int, column: str, value: Any) -> None`**: Actualiza el valor de una celda.
- **`remove_row(index: int) -> bool`**: Elimina una fila por índice.
- **`move_next() -> bool`**: Mueve el cursor a la siguiente fila.
- **`move_previous() -> bool`**: Mueve el cursor a la fila anterior.
- **`current_row` (property) -> `Optional[Dict[str, Any]]`**: Obtiene la fila actual en la posición del cursor.
- **`is_modified(index: Optional[int] = None) -> bool`**: Comprueba si una fila ha sido modificada.
- **`reset_modified(index: Optional[int] = None) -> None`**: Restablece el flag de modificado para una o todas las filas.
- **`lock_row(index: int) -> bool`**: Bloquea una fila específica.
- **`unlock_row(index: int) -> bool`**: Desbloquea una fila.
- **`lock_column(column: str) -> bool`**: Bloquea una columna específica.
- **`unlock_column(column: str) -> bool`**: Desbloquea una columna.
- **`lock_all_rows() -> bool`**: Bloquea todas las filas.
- **`unlock_all_rows() -> bool`**: Desbloquea todas las filas.
- **`lock_all_columns() -> bool`**: Bloquea todas las columnas.
- **`unlock_all_columns() -> bool`**: Desbloquea todas las columnas.
- **`is_row_locked(index: int) -> bool`**: Comprueba si una fila está bloqueada.
- **`is_column_locked(column: str) -> bool`**: Comprueba si una columna está bloqueada.
- **`move_row_to(from_index: int, to_index: int) -> bool`**: Mueve una fila a una posición específica.
- **`move_row_by(index: int, offset: int) -> bool`**: Mueve una fila por un número relativo de posiciones.
- **`move_column_to(column: str, new_index: int) -> bool`**: Mueve una columna a una posición específica.
- **`move_column_by(column: str, offset: int) -> bool`**: Mueve una columna por un número relativo de posiciones.
- **`filter(predicate: Callable[[Dict[str, Any]], bool]) -> 'DataMolder'`**: Filtra filas basándose en un predicado.
- **`map(transform: Callable[[Dict[str, Any]], Dict[str, Any]]) -> 'DataMolder'`**: Transforma filas usando una función de mapeo.
- **`sort(column: str, reverse: bool = False) -> None`**: Ordena las filas en su lugar por una columna.
- **`head(n: int = 5) -> 'DataMolder'`**: Obtiene las primeras `n` filas.
- **`tail(n: int = 5) -> 'DataMolder'`**: Obtiene las últimas `n` filas.
- **`extend(other: 'Data') -> bool`**: Extiende los datos con filas de otra instancia de `Data`.
- **`clear() -> None`**: Elimina todas las filas de los datos.
- **`copy() -> 'DataMolder'`**: Crea una copia profunda de la instancia de datos.
- **`get_size_metrics() -> Dict[str, Any]`**: Obtiene métricas sobre el tamaño y el uso de memoria.
- **`get_distinct_values(column: str) -> Dict[Any, int]`**: Obtiene el recuento de valores distintos en una columna.
- **`get_column_stats(column: str) -> Dict[str, Any]`**: Obtiene información estadística sobre una columna.
- **`pivot(row_column: str, column_values: str, value_column: str) -> 'DataMolder'`**: Crea una tabla pivote.
- **`unpivot(id_columns: List[str], value_name: str = 'value', variable_name: str = 'variable') -> 'DataMolder'`**: Transforma columnas en filas (inverso de pivot).
- **`concatenate(other: 'Data', validate_structure: bool = True) -> 'DataMolder'`**: Concatena dos instancias de `DataMolder` apilando filas.
- **`concat_columns(other: 'Data', validate_rows: bool = True) -> 'DataMolder'`**: Concatena dos instancias de `DataMolder` apilando columnas.
- **`compare(other: 'Data', key_columns: List[str], ignore_columns: List[str] = None) -> Dict[str, Any]`**: Compara dos instancias de `DataMolder` y devuelve sus diferencias.
- **`slice(row_slice: Optional[slice] = None, columns: Optional[List[str]] = None) -> 'DataMolder'`**: Obtiene un subconjunto de los datos por filas y/o columnas.
- **`get_columns(columns: List[str]) -> 'DataMolder'`**: Obtiene un subconjunto de columnas.

### Excepciones

- **`ValidationError(Exception)`**: Excepción base para errores de validación.
- **`TypeValidationError(ValidationError)`**: Excepción lanzada cuando falla la validación de tipo.
- **`ConstraintValidationError(ValidationError)`**: Excepción lanzada cuando falla una validación de restricción.
- **`ColumnNotFoundError(KeyError)`**: Excepción lanzada cuando no se encuentra una columna.