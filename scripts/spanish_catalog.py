from pathlib import Path
import json
root=Path(__file__).resolve().parents[1]
# Reviewed source-text catalog. Protocol identifiers and imported database labels are intentionally unchanged.
pairs=r'''Receiver tools|Herramientas de radio
Quality|Calidad
Channels|Canales
Clips|Clips
More|Más
Listen|Escuchar
Listening|Escuchando
History|Historial
Settings|Ajustes
Explore|Explorar
Explore the band|Explorar la banda
Scan lists|Listas de escaneo
Saved systems|Sistemas guardados
Systems|Sistemas
System|Sistema
Search|Buscar
Search systems|Buscar sistemas
Search talkgroups|Buscar grupos
Search calls|Buscar llamadas
Cancel|Cancelar
Close|Cerrar
Back|Volver
Next|Siguiente
Previous|Anterior
Save|Guardar
Done|Listo
Delete|Eliminar
Remove|Quitar
Edit|Editar
Add|Añadir
Clear|Borrar
Confirm|Confirmar
Start|Iniciar
Stop|Detener
Play|Reproducir
Pause|Pausar
Resume|Continuar
Retry|Reintentar
Refresh|Actualizar
Import|Importar
Export|Exportar
Details|Detalles
Name|Nombre
Source|Fuente
Frequency|Frecuencia
Frequency (MHz)|Frecuencia (MHz)
Gain|Ganancia
Squelch|Silenciador
Bandwidth|Ancho de banda
Automatic|Automático
Manual|Manual
Auto|Auto
Advanced|Avanzado
Appearance|Apariencia
Dark|Oscuro
Light|Claro
Theme|Tema
Units|Unidades
Location|Ubicación
Latitude|Latitud
Longitude|Longitud
Distance|Distancia
Miles|Millas
Kilometers|Kilómetros
Listening mode|Modo de recepción
Analog FM|FM analógica
Narrow FM|FM estrecha
Analog|Analógico
Digital|Digital
All|Todos
None|Ninguno
Any|Cualquiera
Off|Desactivado
On|Activado
on|activado
off|desactivado
Mute|Silenciar
Unmute|Activar audio
Hold|Mantener
Release|Liberar
Skip|Saltar
Avoid|Evitar
Speaker|Altavoz
Phone speaker|Altavoz del teléfono
System default|Predeterminado del sistema
Output|Salida
Audio output|Salida de audio
Output: %1|Salida: %1
Use phone speaker|Usar altavoz del teléfono
Use system audio output|Usar salida de audio del sistema
Audio help|Ayuda de audio
Retry disconnected source|Reconectar la fuente
Receiver disconnected. Reconnect USB, then retry the source.|Receptor desconectado. Reconecta el USB e intenta iniciar la fuente de nuevo.
Start a channel to check reception and audio.|Inicia un canal para comprobar la recepción y el audio.
Replay is playing. Reception and recording continue.|Se está reproduciendo un clip. La recepción y la grabación continúan.
Live audio is muted. Tap Unmute to listen.|El audio en directo está silenciado. Pulsa Activar audio para escuchar.
Media volume is zero. Press the phone volume-up button.|El volumen multimedia está a cero. Sube el volumen con el botón del teléfono.
A call is active without audio. Check encryption, filters and the selected output.|Hay una llamada activa sin audio. Revisa el cifrado, los filtros y la salida seleccionada.
No audio is reaching the player. Check squelch, channel activity and filters.|No llega audio al reproductor. Revisa el silenciador, la actividad del canal y los filtros.
Audio is reaching the player. Choose Phone speaker if the route sounds wrong.|Llega audio al reproductor. Elige el altavoz del teléfono si no se escucha por la salida esperada.
Decode quality|Calidad de decodificación
Last 30 seconds on this frequency|Últimos 30 segundos en esta frecuencia
Start listening to see live measurements|Inicia la recepción para ver las mediciones
Valid control frames: %1 · failed: %2|Tramas de control válidas: %1 · fallidas: %2
Frame success: %1%|Tramas correctas: %1%
Frame success: not enough frames|Tramas correctas: datos insuficientes
Sync losses: %1 · audio gap events: %2|Pérdidas de sincronía: %1 · cortes de audio: %2
Input clipping: %1%|Saturación de entrada: %1%
Input clipping: unavailable|Saturación de entrada: no disponible
SNR: %1 dB|SNR: %1 dB
SNR: unavailable|SNR: no disponible
Control-frame counts apply where the decoder publishes them. Audio gaps count player underruns, not radio silence.|Se muestran las tramas de control que el decodificador informa. Los cortes cuentan interrupciones del reproductor; los periodos sin transmisiones no cuentan.
Improve reception|Mejorar la recepción
Stop automatic gain|Detener ganancia automática
Try automatic gain|Probar ganancia automática
Automatic gain is off|La ganancia automática está desactivada
Waiting for a steady, idle RTL-SDR channel|Esperando un canal RTL-SDR estable sin llamada activa
Waiting for the active call to finish|Esperando a que termine la llamada activa
Measuring original gain for 10 seconds|Midiendo la ganancia original durante 10 segundos
Testing %1 dB; worse results restore the original|Probando %1 dB; si empeora, se restaura la ganancia original
Kept %1 dB: measured quality improved|Se mantiene %1 dB: mejoró la calidad medida
Not enough evidence. Original gain restored.|Datos insuficientes. Se restauró la ganancia original.
No clear improvement. Original gain restored.|Sin mejora clara. Se restauró la ganancia original.
One small gain trial on a steady RTL channel. Calls pause the trial; weak evidence or worse decoding restores the original. Trials are spaced two minutes apart.|Prueba un pequeño cambio de ganancia en un canal RTL estable. Las llamadas pausan la prueba. Si faltan datos o empeora la decodificación, se restaura el valor original. Hay dos minutos entre pruebas.
Turn site selection off|Desactivar selección de sitios
Choose sites automatically|Elegir sitios automáticamente
Automatic site selection is off|La selección automática de sitios está desactivada
Watching saved sites in this system|Evaluando los sitios guardados de este sistema
Keeping this site until the call or hold ends|Se mantiene este sitio hasta que termine la llamada o se libere la retención
Kept the site with better measured decoding|Se mantiene el sitio con mejor decodificación medida
Trial was not better. Returning to the previous site.|La prueba no mejoró la recepción. Volviendo al sitio anterior.
Checking %1; reception briefly restarts|Comprobando %1; la recepción se reinicia brevemente
Import another eligible site in the same RadioReference system|Importa otro sitio compatible del mismo sistema de RadioReference
Uses saved sites in the same RadioReference system. A trial briefly restarts reception. Calls and holds take priority; unsuccessful trials return to the previous site.|Usa sitios guardados del mismo sistema de RadioReference. Cada prueba reinicia brevemente la recepción. Las llamadas y las retenciones tienen prioridad; si no mejora, vuelve al sitio anterior.
Channel filters|Filtros de canal
Blank means any. Filters apply to audio on this exact frequency. Tone detection needs a few seconds; use at least 3 seconds of scan dwell. Raw recordings keep the original signal.|Un campo vacío permite cualquier valor. Los filtros controlan el audio de esta frecuencia exacta. Detectar tonos tarda unos segundos; usa al menos 3 segundos de permanencia por canal. Las grabaciones sin procesar conservan la señal original.
Load current channel|Cargar canal actual
CTCSS tone (Hz) — narrow FM|Tono CTCSS (Hz) — FM estrecha
Any tone|Cualquier tono
DCS code — use instead of CTCSS|Código DCS — usar en lugar de CTCSS
Any code, or 023|Cualquier código, o 023
Normal DCS|DCS normal
Inverted DCS|DCS invertido
DCS uses three octal digits, for example 023.|DCS usa tres dígitos octales, por ejemplo 023.
DMR color code (0–15)|Código de color DMR (0–15)
Any color code|Cualquier código de color
Both time slots|Ambos intervalos de tiempo
Time slot 1|Intervalo de tiempo 1
Time slot 2|Intervalo de tiempo 2
Talkgroup ID|ID de grupo
Any talkgroup|Cualquier grupo
Apply filter|Aplicar filtro
Filter saved and active|Filtro guardado y activo
Clear this channel's filters|Borrar filtros de este canal
Filters cleared|Filtros borrados
Check the frequency, tone, color code, slot and talkgroup.|Revisa la frecuencia, el tono, el código de color, el intervalo y el grupo.
The filter limit is 500 channels.|El límite de filtros es de 500 canales.
Could not save filters.|No se pudieron guardar los filtros.
Discovery notebook|Registro de señales
Pause discoveries|Pausar registro
Remember discoveries|Registrar señales
Stores up to 500 observations on this phone. Energy alone is unconfirmed. Three consecutive observations are required; scanning too quickly may miss entries.|Guarda hasta 500 observaciones en este teléfono. Detectar energía no confirma el protocolo. Se requieren tres observaciones consecutivas; un escaneo muy rápido puede omitir señales.
Export notebook|Exportar registro
Clear notebook|Borrar registro
Clear notebook?|¿Borrar el registro?
This removes stored observations from this phone.|Se borrarán las observaciones guardadas en este teléfono.
Unconfirmed energy|Energía sin confirmar
First: %1\nLast: %2|Primera vez: %1\nÚltima vez: %2
Talkgroup: %1 · radio: %2|Grupo: %1 · radio: %2
Save listening preset|Guardar canal de escucha
Listening preset saved|Canal de escucha guardado
Could not save preset|No se pudo guardar el canal
Discovery %1 MHz|Señal %1 MHz
Notebook saved|Registro guardado
Replay received audio|Reproducir audio recibido
Received audio replay|Repetición de audio recibido
%1 seconds buffered. Reception, scanning and recording continue during playback.|%1 segundos almacenados. La recepción, el escaneo y la grabación continúan durante la reproducción.
Replay last 30 seconds|Repetir los últimos 30 segundos
Replay last 60 seconds|Repetir los últimos 60 segundos
Replay requested|Reproducción solicitada
Replay 30 s|Repetir 30 s
Replay 60 s|Repetir 60 s
Stop replay|Detener repetición
Return to live|Volver al audio en directo
Save audio clip|Guardar clip de audio
Save WAV|Guardar WAV
Save received audio|Guardar audio recibido
Audio saved|Audio guardado
Playing received audio|Reproduciendo audio recibido
Clear buffer|Vaciar memoria de audio
Silent gaps are omitted. Playback returns to live automatically when the clip ends.|Se omiten los periodos de silencio. Al terminar el clip, vuelve automáticamente al audio en directo.
Choose 1–60 seconds.|Elige entre 1 y 60 segundos.
No received audio in the replay buffer yet.|Todavía no hay audio recibido en la memoria.
Could not finish writing the clip.|No se pudo terminar de guardar el clip.
Playback could not start.|No se pudo iniciar la reproducción.
Capture raw signal|Capturar señal sin procesar
Capture this channel for up to 20 seconds or 64 MB. The receiver briefly restarts before and after capture. Start from a single channel, not a scan list. Saved files include I/Q data and tuning metadata.|Captura este canal durante un máximo de 20 segundos o 64 MB. El receptor se reinicia brevemente antes y después. Inicia desde un solo canal, fuera de una lista de escaneo. Los archivos incluyen datos I/Q y los ajustes de sintonización.
Capture current signal|Capturar señal actual
Finish capture and resume|Terminar captura y continuar
Export signal and metadata|Exportar señal y metadatos
Capture exported|Captura exportada
Use a live RTL-SDR or Airspy source without custom I/Q arguments.|Usa una fuente RTL-SDR o Airspy en directo sin argumentos I/Q personalizados.
At least 150 MB of free storage is needed.|Se necesitan al menos 150 MB de almacenamiento libre.
Capturing up to 20 seconds or 64 MB. Reception briefly restarts.|Capturando hasta 20 segundos o 64 MB. La recepción se reinicia brevemente.
Capture stopped. Export both I/Q and metadata together.|Captura detenida. Exporta los datos I/Q junto con sus metadatos.
Capture no longer available.|La captura ya no está disponible.
Stop reception before exporting a capture.|Detén la recepción antes de exportar una captura.
Capture filename is too long.|El nombre del archivo de captura es demasiado largo.
Could not finish the capture export.|No se pudo terminar de exportar la captura.
Change the language at any time. Protocol names and database labels stay as supplied.|Cambia el idioma cuando quieras. Los nombres de protocolos y las etiquetas de la base de datos conservan su idioma original.
Advanced receiver tools|Herramientas avanzadas de radio
Receiver profiles, manual gain comparison, local site map, activity alerts and portable backup.|Perfiles del receptor, comparación manual de ganancia, mapa local de sitios, avisos de actividad y copia de seguridad.
Open advanced tools|Abrir herramientas avanzadas
Quality, channels, clips and audio help|Calidad, canales, clips y ayuda de audio
Receiver profiles|Perfiles del receptor
Name profiles for each dongle, antenna and band. Applying one changes defaults for the next session.|Crea perfiles para cada receptor, antena y banda. Al aplicar uno, cambian los valores predeterminados de la siguiente sesión.
Example: RTL V3 · VHF roof antenna|Ejemplo: RTL V3 · antena VHF de techo
Save current defaults|Guardar ajustes actuales
Profile saved|Perfil guardado
Check the name and receiver settings.|Revisa el nombre y los ajustes del receptor.
Profile applied to next-session defaults|Perfil aplicado a los ajustes de la siguiente sesión
No stable tone identified|No se ha identificado un tono estable
Reception comparison|Comparación de recepción
Compare gain|Comparar ganancia
Cancel and restore|Cancelar y restaurar
Testing %1 dB · %2 s|Probando %1 dB · %2 s
Input %1 dBFS · clipping %2%|Entrada %1 dBFS · saturación %2%
Input level unavailable|Nivel de entrada no disponible
insufficient frames|tramas insuficientes
Use %1 dB|Usar %1 dB
Portable backup|Copia de seguridad portátil
Save backup|Guardar copia de seguridad
Restore backup|Restaurar copia de seguridad
Save XeraX backup|Guardar copia de XeraX
Restore XeraX backup|Restaurar copia de XeraX
Backup saved|Copia de seguridad guardada
Backup restored|Copia de seguridad restaurada
Activity alerts|Avisos de actividad
Save alert rules|Guardar reglas de avisos
Alert rules saved|Reglas de avisos guardadas
Phone health|Estado del teléfono
Battery: %1% · thermal level: %2 · battery saver: %3|Batería: %1% · nivel térmico: %2 · ahorro de batería: %3
Local site map · Indio, 50 mi|Mapa de sitios · Indio, 50 mi
Import or save sites with location metadata to populate this map.|Importa o guarda sitios con datos de ubicación para verlos en este mapa.
Open source licenses|Licencias de código abierto
Diagnostics|Diagnóstico
USB RTL-SDR|RTL-SDR por USB
Airspy R2 / Mini|Airspy R2 / Mini
Talkgroups|Grupos de conversación
Recent calls|Llamadas recientes
No calls yet|Aún no hay llamadas
Encrypted|Cifrado
Clear audio|Audio sin cifrar
Control channel|Canal de control
Voice channel|Canal de voz
Scanning|Escaneando
Scan|Escanear
Priority|Prioridad
Add channel|Añadir canal
Add system|Añadir sistema
New scan list|Nueva lista de escaneo
Keep screen awake|Mantener pantalla encendida
RadioReference account|Cuenta de RadioReference
Sign in|Iniciar sesión
Sign out|Cerrar sesión
Username|Nombre de usuario
Password|Contraseña
Country|País
State|Estado
County|Condado
Agency|Agencia
Category|Categoría
Sites|Sitios
Conventional channels|Canales convencionales
Import selected|Importar selección
Select all|Seleccionar todo
Clear selection|Borrar selección
Listen to %1|Escuchar %1
Play %1|Reproducir %1
Stop listening|Detener recepción
Listen port|Puerto de escucha
Port|Puerto
Host|Servidor
Enter a whole number.|Introduce un número entero.
Start a single RTL-SDR channel in Explore before comparing gain. Airspy uses its own gain controls.|Inicia un solo canal RTL-SDR en Explorar para comparar la ganancia. Airspy tiene sus propios controles.
Original gain restored. Compare clipping and CRC success; changing radio traffic can affect the result.|Ganancia original restaurada. Compara la saturación y los aciertos CRC; los cambios en el tráfico pueden afectar al resultado.
Gain command was rejected.|Se rechazó el cambio de ganancia.
Comparison canceled because the channel changed.|Se canceló la comparación porque cambió el canal.
Try five gain settings on the same frequency. Each settles for 2 seconds, then measures for 10 seconds. Use an active channel; CRC results need at least 10 control frames. No gain setting can restore an overloaded signal.|Prueba cinco ajustes de ganancia en la misma frecuencia. Cada uno se estabiliza 2 segundos y mide durante 10. Usa un canal activo; los resultados CRC requieren al menos 10 tramas de control. La ganancia no puede reparar una señal saturada.
%1 seconds buffered · up to 60 seconds · silent gaps omitted. Reception continues during replay; save a WAV at any time.|%1 segundos almacenados · hasta 60 segundos · se omiten silencios. La recepción continúa durante la repetición; puedes guardar un WAV cuando quieras.
Offline position plot of your saved sites. North is up. Blue: saved, green: digital call observed, gray: avoided. Database locations may be coverage centers.|Mapa sin conexión de los sitios guardados, con el norte arriba. Azul: guardado; verde: llamada digital observada; gris: evitado. Las ubicaciones pueden ser centros de cobertura.
Merge saved systems, scan lists, CSV labels and receiver defaults onto another phone. Accounts, radio keys and recordings are excluded. Existing systems remain; restored copies get new IDs. Imported target CSVs become editable lists; lists with scoped CSV options need a separate CSV export.|Combina sistemas, listas de escaneo, etiquetas CSV y ajustes del receptor en otro teléfono. Se excluyen cuentas, claves de radio y grabaciones. Se conservan los sistemas existentes; las copias reciben nuevos ID. Los CSV de destinos se convierten en listas editables; los que tienen opciones por ámbito requieren una exportación CSV aparte.
Enter talkgroups and radio IDs, for example tg:1234, rid:5678. Alerts match across systems, need Android notification permission, and repeat at most once per 30 seconds. Clear the field to disable.|Introduce grupos e ID de radio, por ejemplo tg:1234, rid:5678. Los avisos se aplican a todos los sistemas, requieren permiso de notificaciones de Android y se repiten como máximo cada 30 segundos. Vacía el campo para desactivarlos.
Use tg: or rid: followed by a number from 1 to 16777215, up to 64 rules.|Usa tg: o rid: seguido de un número de 1 a 16777215, con un máximo de 64 reglas.'''
pairs += r'''
Clip created: %1|Clip creado: %1
Another app has audio focus. Audio resumes when focus returns.|Otra aplicación está usando el audio. La reproducción continuará cuando libere el audio.
Gain changed outside the trial. Automatic gain stopped.|La ganancia cambió fuera de la prueba. Se detuvo la ganancia automática.
Site could not start. Returning to the previous site.|No se pudo iniciar el sitio. Volviendo al sitio anterior.
The latest 30 entries appear below. Export includes the full notebook.|Abajo aparecen las últimas 30 entradas. La exportación incluye todo el registro.
ADP / ARC4 (40-bit)|ADP / ARC4 (40 bits)
ADP / ARC4 needs exactly 10 hexadecimal digits (40 bits), including leading zeros.|ADP / ARC4 requiere exactamente 10 dígitos hexadecimales (40 bits), incluidos los ceros iniciales.
ADP / ARC4: enter the supplied 40-bit key as 10 hex digits. P25 Phase 1/2 uses ALG AA; DMR Enhanced Privacy uses ALG 21. Key IDs identify keys; they are not the key itself.|ADP / ARC4: introduce la clave de 40 bits como 10 dígitos hexadecimales. P25 Fase 1/2 usa ALG AA; la privacidad mejorada de DMR usa ALG 21. El ID identifica la clave; no es la clave.
Use 10 hexadecimal digits for the ADP / ARC4 key, including leading zeros.|Usa 10 dígitos hexadecimales para la clave ADP / ARC4, incluidos los ceros iniciales.
ADP / ARC4 privacy|Privacidad ADP / ARC4
P25 Phase 1/2 ADP and DMR Enhanced Privacy use the supplied 40-bit key. Create a profile here, then select it under Decryption keys in your saved system.|ADP de P25 Fase 1/2 y la privacidad mejorada de DMR usan la clave de 40 bits proporcionada. Crea un perfil aquí y selecciónalo en Claves de descifrado dentro de tu sistema guardado.
Create ADP / ARC4 profile|Crear perfil ADP / ARC4
ADP profile saved. Select it under Decryption keys for your system.|Perfil ADP guardado. Selecciónalo en Claves de descifrado de tu sistema.
RC4 / DES (general)|RC4 / DES (general)
Decryption profile|Perfil de descifrado
Auto / mixed|Auto / mixto
Profile name|Nombre del perfil
Protocol|Protocolo
Profile protocol|Protocolo del perfil
Key selection|Selección de claves
Key source|Fuente de claves
Automatic keys|Claves automáticas
Direct override|Clave directa
Advanced vendor mode|Modo avanzado del fabricante
No keys|Sin claves
Direct key format|Formato de clave directa
Key configured. Leave the replacement field blank to keep it.|Clave configurada. Deja vacío el campo de reemplazo para conservarla.
Replacement key material|Nueva clave de reemplazo
Replacement material; blank keeps current|Clave de reemplazo; vacío conserva la actual
Key material|Clave
Vendor mode|Modo del fabricante
Vendor key material|Clave del fabricante
Key label|Nombre de la clave
Key format|Formato de clave
Key lookup|Búsqueda de clave
Received key ID|ID de clave recibido
Legacy destination ID|ID de destino heredado
Destination ID (decimal)|ID de destino (decimal)
Key ID (hex)|ID de clave (hexadecimal)
Use this key|Usar esta clave
Remove key from draft|Quitar clave del borrador
Decryption keys|Claves de descifrado
Profile missing — choose another profile|Falta el perfil — elige otro
No profile selected|Ningún perfil seleccionado
No profile|Sin perfil
Create profile|Crear perfil
Manage profile|Administrar perfil
Key %1|Clave %1
Key configured|Clave configurada
Privacy / encryption key|Clave de privacidad / cifrado
Keep|Conservar
Replace|Reemplazar
Keep current material|Conservar clave actual
Basic · 0–255|Básica · 0–255
Enhanced · RC4|Mejorada · RC4
Scrambler · 0–32767|Mezclador · 0–32767
DONGLE ERROR|ERROR DEL RECEPTOR
DONGLE READY|RECEPTOR LISTO
NO DONGLE|SIN RECEPTOR
Plug in an RTL-SDR, then tap Connect.|Conecta un RTL-SDR y pulsa Conectar.
Connect|Conectar
Play again|Reproducir de nuevo
key configured|clave configurada
Refresh from RadioReference to enable site grouping|Actualiza desde RadioReference para agrupar sitios
Choose sites for %1|Elegir sitios para %1
1 site|1 sitio
%1 sites|%1 sitios
More options for %1|Más opciones para %1
+ Add a system|+ Añadir un sistema
USB, Airspy, network or file|USB, Airspy, red o archivo
+ Add a scan list|+ Añadir lista de escaneo
Or go looking|O busca señales
Edit Explore connection|Editar conexión de Explorar
USB dongle|Receptor USB
%1 · from %2 MHz|%1 · desde %2 MHz
Tune around and find what is on the air|Sintoniza y descubre las transmisiones
Add a system|Añadir un sistema
Set up manually|Configurar manualmente
Import from RadioReference|Importar desde RadioReference
Remove…|Eliminar…
Remove list|Eliminar lista
This deletes the scan list and its settings. Imported files stay in the library.|Se elimina la lista de escaneo y sus ajustes. Los archivos importados se conservan.
Remove %1?|¿Eliminar %1?
Remove system|Eliminar sistema
Scan list removal failed|No se pudo eliminar la lista
The decoder has not confirmed the change. The switch shows its current setting.|El decodificador no ha confirmado el cambio. El interruptor muestra el ajuste actual.
Could not change the running decoder's setting. Try again.|No se pudo cambiar el ajuste del decodificador. Inténtalo de nuevo.
Enter seconds from 0 to 30, e.g. 2.0.|Introduce de 0 a 30 segundos, por ejemplo 2.0.
Follows your phone's dark mode schedule.|Sigue el horario de modo oscuro del teléfono.
Use metric units|Usar unidades métricas
Distances in kilometers (km)|Distancias en kilómetros (km)
Distances in miles (mi)|Distancias en millas (mi)
Output is no longer available. Choose another output.|La salida ya no está disponible. Elige otra.
Save skipped talkgroups|Guardar grupos omitidos
Applies to Skip immediately. Off keeps avoids until stop or list reload. Talkgroup-list edits still save.|Se aplica a Saltar de inmediato. Desactivado, las omisiones duran hasta detener la recepción o recargar la lista. Las ediciones de grupos se siguen guardando.
Clear temporary TG avoids — current list (%1)|Borrar omisiones temporales — lista actual (%1)
Could not clear temporary avoids. Try again.|No se pudieron borrar las omisiones temporales. Inténtalo de nuevo.
Keep listening in background|Escuchar en segundo plano
Notification controls are available when permission is allowed|Los controles de notificación están disponibles con el permiso correspondiente
Start when a dongle is attached|Iniciar al conectar un receptor
Resume the last USB system or scan list|Continuar el último sistema USB o lista de escaneo
Decoding · next start|Decodificación · próximo inicio
Skip encrypted calls|Omitir llamadas cifradas
Enabled talkgroups can play when keys are usable. Explicit exclusions stay blocked.|Los grupos habilitados pueden escucharse si hay claves utilizables. Las exclusiones explícitas permanecen bloqueadas.
Auto tuner correction|Corrección automática de sintonía
Fixes frequency drift on long runs|Corrige la desviación de frecuencia en sesiones largas
Voice hang time|Tiempo de espera tras la voz
Keeps a call's channel after voice stops. Also sets channel-scanning dwell (-Y); scan lists have separate dwell settings.|Mantiene el canal después de terminar la voz. También fija la permanencia de escaneo (-Y); las listas tienen ajustes separados.
Radio defaults · next start|Ajustes de radio · próximo inicio
Tuner gain|Ganancia del sintonizador
PPM correction|Corrección PPM
Bias tee|Alimentación por coaxial
Powers an external LNA|Alimenta un amplificador LNA externo
Extra decoder arguments|Argumentos adicionales del decodificador
e.g. -C chan.csv -G group.csv|por ejemplo -C chan.csv -G group.csv
Libraries|Bibliotecas
Imported files|Archivos importados
Channel maps, talkgroups, keys, band plans, radio IDs|Mapas de canales, grupos, claves, planes de banda e ID de radio
Account|Cuenta
Username and application key|Usuario y clave de aplicación
About & support|Información y ayuda
Current process and previous-run tail; not crash/ANR capture|Proceso actual y final de la sesión anterior; no incluye informes de fallos/ANR
Version|Versión
Version copied|Versión copiada
This profile uses a direct or no-key configuration. Choose Automatic keys before adding entries selected by received ID.|Este perfil usa una clave directa o ninguna. Elige Claves automáticas para añadir entradas seleccionadas por el ID recibido.
This profile uses an imported CSV. Update that file in Imported files, or choose Manage keys here to build a replacement collection.|Este perfil usa un CSV importado. Actualízalo en Archivos importados o elige Administrar claves aquí para crear otra colección.
Choose automatic keys and managed talkgroup overrides before editing a mapping here. Imported mappings can be updated in Imported files.|Elige claves automáticas y asignaciones de grupos administradas para editar aquí. Las asignaciones importadas se actualizan en Archivos importados.
Legacy configuration retained. Changing a direct key type requires replacement material.|Se conserva la configuración heredada. Cambiar el tipo de clave directa requiere introducir una nueva clave.
Use the received key ID for each call where supported. An empty collection means no keys supplied.|Usa el ID de clave recibido de cada llamada cuando sea compatible. Una colección vacía indica que no hay claves proporcionadas.
A direct override disables automatic key loading. It applies to the configured channel or session, not an individual talkgroup.|Una clave directa desactiva la carga automática. Se aplica al canal o a la sesión configurada, no a un grupo individual.
Standalone DMR session only. Vendor modes force their own processing; stop and restart to change them. They cannot be assigned to scan entries or changed live.|Solo para sesiones DMR independientes. Los modos del fabricante fuerzan su procesamiento; detén y reinicia para cambiarlos. No se pueden asignar al escaneo ni cambiar en directo.
No key material will be installed by this profile. Received encryption status and listening policy are separate.|Este perfil no instalará claves. El estado de cifrado recibido y las preferencias de escucha son independientes.
The direct key does not match this protocol and key format.|La clave directa no coincide con el protocolo o el formato.
A key has an unsupported format or width.|Una clave tiene un formato o una longitud no compatible.
Invalid decimal key material.|Clave decimal no válida.
Automatic · received key ID|Automático · ID de clave recibido
Waiting for received audio.|Esperando audio recibido.
Automatic saved keys|Claves guardadas automáticas
A received key ID selects a matching key from your assigned profile. A match means a saved key is available; it does not verify its value. Missing keys stay unavailable.|El ID de clave recibido selecciona una clave coincidente del perfil asignado. La coincidencia indica que hay una clave guardada; no confirma que su valor sea correcto. Las claves faltantes siguen sin estar disponibles.
Set up automatic P25 / DMR keys|Configurar claves automáticas P25 / DMR
Set up NXDN scrambler keys|Configurar claves de scrambler NXDN
NXDN scrambler values are decimal 0–32767. NXDN48 can match a received key ID (hex 00–3F); destination mappings also support NXDN96. Use a direct profile for a fixed supplied value.|Los valores de scrambler NXDN son decimales de 0 a 32767. NXDN48 puede usar un ID de clave recibido (hex 00–3F); las asignaciones por destino también admiten NXDN96. Usa un perfil directo para un valor fijo proporcionado.
Key profile saved. Select it under Decryption keys for your system.|Perfil de claves guardado. Selecciónalo en Claves de descifrado de tu sistema.'''
pairs += "\n"+(root/"scripts/spanish_expansion.txt").read_text(encoding="utf-8-sig").strip()
catalog={}
pairs += "\n"+(root/"scripts/spanish_414.txt").read_text(encoding="utf-8-sig").strip()
pairs += "\n"+(root/"scripts/spanish_415.txt").read_text(encoding="utf-8-sig").strip()
pairs += "\n"+(root/"scripts/spanish_420.txt").read_text(encoding="utf-8-sig").strip()
pairs += "\n"+(root/"scripts/spanish_430.txt").read_text(encoding="utf-8-sig").strip()
pairs += "\n"+(root/"scripts/spanish_windows.txt").read_text(encoding="utf-8-sig").strip()
pairs += "\n"+(root/"scripts/spanish_431.txt").read_text(encoding="utf-8-sig").strip()
for line in pairs.splitlines():
    en,es=line.split('|',1);catalog[en.replace(r'\n','\n')]=es.replace(r'\n','\n')
p=root/'upstream/dsd-neo/src/ui/qt/i18n/es.json';p.parent.mkdir(exist_ok=True)
p.write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(f'{len(catalog)} Spanish translations')
