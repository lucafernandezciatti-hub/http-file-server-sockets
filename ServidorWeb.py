from socket import *
import sys
import os
from urllib.parse import parse_qs, urlparse
import qrcode
import mimetypes
import gzip
import time

#FUNCIONES AUXILIARES

contraseña = "DINASTIA"

def imprimir_qr_en_terminal(url):
    """Dada una URL la imprime por terminal como un QR"""
    data = url
    qr = qrcode.QRCode(box_size = 1, border = 1) # Configuramos el diseño del QR
    qr.add_data(data)
    qr.print_ascii() # Imprimimos el QR en formato de texto ASCII

def get_wifi_ip():
    """Obtiene la IP local asociada a la interfaz de red (por ejemplo, Wi-Fi)."""
    s = socket(AF_INET, SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip #Devuelve la IP como string

def parsear_multipart(body, boundary):
    """Función auxiliar (ya implementada) para parsear multipart/form-data."""
    try:
        # Se divide el cuerpo por el boundary para luego poder extraer el nombre y contenido del archivo
        parts = body.split(f'--{boundary}'.encode())
        for part in parts:
            if b'filename=' in part:
                # Se extrae el nombre del archivo
                filename_start = part.find(b'filename="') + len(b'filename="')
                filename_end = part.find(b'"', filename_start)
                filename = part[filename_start:filename_end].decode()

                # Se extrae el contenido del archivo que arranca después de los headers
                header_end = part.find(b'\r\n\r\n')
                if header_end == -1:
                    header_end = part.find(b'\n\n')
                    content_start = header_end + 2
                else:
                    content_start = header_end + 4

                # El contenido va hasta el último CRLF antes del boundary
                content_end = part.rfind(b'\r\n')
                if content_end <= content_start:
                    content_end = part.rfind(b'\n')

                file_content = part[content_start:content_end]
                if filename and file_content:
                    return filename, file_content
        return None, None
    except Exception as e:
        print(f"Error al parsear multipart: {e}")
        return None, None

def generar_html_interfaz(modo): # Lo único que modificamos de esta función fue agregarle action="/upload" 
# Para distinguir el POST del formulario con la contraseña y el POST de la subida del archivo
    """
    Genera el HTML de la interfaz principal:
    - Si modo == 'download': incluye un enlace o botón para descargar el archivo.
    - Si modo == 'upload': incluye un formulario para subir un archivo.
    """
    if modo == 'download':
        return """
<html>
  <head>
    <meta charset="utf-8">
    <title>Descargar archivo</title>
    <style>
      body { font-family: sans-serif; max-width: 500px; margin: 50px auto; }
      a { display: inline-block; padding: 10px 20px; background: #007bff; color: white; text-decoration: none; border-radius: 5px; }
    </style>
  </head>
  <body>
    <h1>Descargar archivo</h1>
    <p>Haz click en el botón para descargar:</p>
    <a href="/download">Descargar archivo</a>
  </body>
</html>
"""
    
    else:  # upload
        return """
<html>
  <head>
    <meta charset="utf-8">
    <title>Subir archivo</title>
    <style>
      body { font-family: sans-serif; max-width: 500px; margin: 50px auto; }
      form { border: 2px dashed #ccc; padding: 20px; border-radius: 5px; }
      input[type="submit"] { padding: 10px 20px; background: #28a745; color: white; border: none; border-radius: 5px; cursor: pointer; }
    </style>
  </head>
  <body>
    <h1>Subir archivo</h1>
    <form method="POST" action="/upload" enctype="multipart/form-data"> 
      <input type="file" name="file" required>
      <input type="submit" value="Subir">
    </form>
  </body>
</html>
"""

def generar_html_password(): # Generamos el html que envía el formulario para rellenar con la contraseña
# Lo diseñamos de forma que la respuesta se envíe a la ruta /autenticacion
    return """
<html>
  <head>
    <meta charset="utf-8">
    <title>Autenticación</title>
  </head>
  <body>
    <h2>Ingresar contraseña</h2>
    <form method="POST" action="/autenticacion">
      <input type="password" name="contra" placeholder="Contraseña" required>
      <input type="submit" value="Ingresar">
    </form>
  </body>
</html>
"""

def manejar_descarga(archivo, request_line, gzip_status):
    """
    Genera una respuesta HTTP con el archivo solicitado. 
    Si el archivo no existe debe devolver un error.
    Debe incluir los headers: Content-Type, Content-Length y Content-Disposition.
    """
    files_folder = "archivos_servidor" 
    nombre_archivo = os.path.basename(archivo) # Extraemos el nombre del archivo de la ruta insertada por parámetro
    ruta_download = os.path.join(files_folder,nombre_archivo) # Creamos una ruta válida para conectar el directorio origen con el nombre del archivo a descargar
    header_content_encoding = b""

    if os.path.isfile(ruta_download): # Verificamos que el archivo exista y que efectivamente sea un archivo y no un directorio
        with open(ruta_download, "rb") as f: # Abrimos el archivo y lo leemos en bytes
            contenido = f.read()
            if gzip_status: # Comprobamos si la opción de comprimir está activa
                contenido = gzip.compress(contenido, compresslevel=6) # Comprimimos el archivo 
                header_content_encoding = b"Content-Encoding: gzip\r\n" # Agregamos el header correspondiente

        tipo = mimetypes.guess_type(ruta_download)[0]  # Tomamos el tipo del archivo MIME.
       
        content_type = tipo.encode() # Convertimos en bytes.

        # Configuramos los headers
        header_estado = b"HTTP/1.1 200 OK\r\n"
        header_content_type = b"Content-Type: " + content_type + b"\r\n"

        header_content_length = (
            b"Content-Length: " + str(len(contenido)).encode() + b"\r\n"
        )

        nombre_bytes = nombre_archivo.encode()
        header_content_disposition = (
            b"Content-Disposition: attachment; filename=\"" + nombre_bytes + b"\"\r\n"
        )

    else: # En caso de que la ruta indicada por parámetro no se encuentre en la carpeta "archivos_servidor" o no sea un archivo, enviamos html 404 Not Found
        contenido = b"<h1>404 - Archivo no encontrado</h1>"

        header_estado = b"HTTP/1.1 404 Not Found\r\n"
        header_content_type = b"Content-Type: text/html\r\n"
        header_content_length = (
            b"Content-Length: " + str(len(contenido)).encode() + b"\r\n"
        )
        header_content_disposition = b""

    # Juntamos los headers
    headers = (
        header_estado +
        header_content_type +
        header_content_length +
        header_content_disposition +
        header_content_encoding +
        b"\r\n"
    )

    # Enviamos headers y contenido
    return headers+contenido


def manejar_carga(body, boundary, directorio_destino="."):
    """
    Procesa un POST con multipart/form-data, guarda el archivo y devuelve una página de confirmación.
    """
    # Usamos la función auxiliar brindada para conseguir el nombre del archivo y el contenido
    nombre_archivo, contenido_archivo = parsear_multipart(body, boundary) 

    if nombre_archivo is None or contenido_archivo is None: # Si la función parsear_multipart no encuentra el nombre o el contenido del archivo, devolvemos html de error
    # Tomamos el error como Bad Request porque surge de no poder interpretar la request del cliente
        html_error = b"<h1>Error: no se pudo procesar el archivo</h1>"

        headers = (
            b"HTTP/1.1 400 Bad Request\r\n"
            b"Content-Type: text/html\r\n"
            b"Content-Length: " + str(len(html_error)).encode() + b"\r\n"
            b"\r\n"
        )
        return headers + html_error
    
    ruta_destino = os.path.join(directorio_destino, nombre_archivo) # Conectamos en una ruta el nombre del archivo subido con el directorio destino

    with open(ruta_destino, "wb") as f: # Escribimos el archivo en bytes 
        f.write(contenido_archivo)

    mensaje = f"<h1>Archivo '{nombre_archivo}' cargado correctamente</h1>"
    cuerpo_html = mensaje.encode()

    # Configuramos los headers correspondientes
    headers = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: text/html\r\n"
        b"Content-Length: " + str(len(cuerpo_html)).encode() + b"\r\n"
        b"\r\n"
    )

    return headers + cuerpo_html



def start_server(archivo_descarga=None, modo_upload=False):

    ip_server = get_wifi_ip() # Obtenemos la IP para el servidor con la función auxiliar brindada
    server_socket = socket(AF_INET, SOCK_STREAM) # Creamos el socket del servidor
    server_socket.bind((ip_server, 0)) # Le asignamos la IP al socket y dejamos que el sistema operativo elija el puerto
    puerto = server_socket.getsockname()[1] 
    server_socket.listen(1) # Ponemos el socket a escuchar requests

    if modo_upload:
        print("Servidor en modo carga (upload)")
    else:
        print("Servidor en modo descarga (download)")

    url = f"http://{ip_server}:{puerto}/" # Creamos la url que direcciona al servidor
    print(url)
    imprimir_qr_en_terminal(url) # Imprimimos la url como QR

    while True: # Abrimos un ciclo While True para sólo cerrar el socket del servidor luego de una descarga o una carga
        client_socket, client_addr = server_socket.accept() # Creamos el socket para el primer cliente que mande request
        raw_request = client_socket.recv(4096) # Recibimos hasta 4096 bytes del request del cliente

        T0 = time.perf_counter_ns() # Iniciamos timer para la experimentación con gzip

        if not raw_request: # Si falla la recepción de bytes del request se cierra el socket
            client_socket.close()
            continue

        request = raw_request.decode() # Convertimos la request a string

        request_line = request.split("\r\n")[0] # Separamos las líneas del request y obtenemos la primera 

        try:
            metodo, ruta, _ = request_line.split(" ") # Obtenemos el metodo y la ruta de la primera linea del request
        except: # Si falla la obtención del método o la ruta cerramos el socket del cliente
            client_socket.close() 
            continue # Se acepta otra request

        if metodo == "GET" and ruta == "/": # Si es la primera request del cliente se le envía el html pidiendo la contraseña
            html = generar_html_password().encode()
            response = (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: text/html\r\n"
                b"Content-Length: " + str(len(html)).encode() + b"\r\n"
                b"\r\n"
                + html
            )
            client_socket.sendall(response)
            client_socket.close()
            continue # Se acepta otra request

        
        if metodo == "POST" and ruta == "/autenticacion": # Se procesa el formulario con la contraseña enviado por el cliente
            try:
                headers, body = request.split("\r\n\r\n", 1) # Se separa la request del cliente en headers y body
                params = parse_qs(body) # Se crea un diccionario en donde las claves son los diferentes campos del formulario y los valores asociados son la respuestas del cliente en dichos campos
                contra = params.get("contra", [""])[0] # Se obtiene la respuesta para el campo de contraseña 
            
            except: # Si falla algo, se toma la contraseña como nula
                contra = ""

            if contra != contraseña: # Si la contraseña ingresada es incorrecta, negamos la request del cliente mediante el status 403 Forbidden
                cuerpo = "<h1>Contraseña incorrecta</h1>"
                cuerpo_en_bytes = cuerpo.encode("utf-8")
                response = (
                    b"HTTP/1.1 403 Forbidden\r\n"
                    b"Content-Type: text/html; charset=utf-8\r\n"
                    b"Content-Length: " + str(len(cuerpo_en_bytes)).encode() + b"\r\n"
                    b"\r\n"
                    + cuerpo_en_bytes
                )
                client_socket.sendall(response)
                client_socket.close()
                continue # Se acepta otra request

            if modo_upload: # Si se aceptó la contraseña se envía el html correspondiente según el modo del servidor
                html = generar_html_interfaz("upload").encode()
            else:
                html = generar_html_interfaz("download").encode()

            response = (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: text/html\r\n"
                b"Content-Length: " + str(len(html)).encode() + b"\r\n"
                b"\r\n"
                + html
            )
            client_socket.sendall(response)
            client_socket.close()
            continue # Se acepta otra request

        if metodo == "GET" and ruta == "/download" and archivo_descarga is not None: # Caso en que la request es para descargar un archivo

            gzip_accept = False 
            # Verificamos si el cliente acepta compresión gzip buscando el header "Accept-Encoding", procurando que éste contenga "gzip"
            for linea in request.split("\r\n"):  
                if linea[:16] == ("Accept-Encoding:") and "gzip" in linea: 
                    gzip_accept = True

            gzip_activo = False
            if "--comprimir" in sys.argv: # Verificamos si se activó la opción de comprimir con el comando en terminal
                gzip_activo = True # Activamos la compresión

            # Generamos la response HTTP con la función manejar_descarga que devuelve el archivo y los headers correspondientes
            response_h = manejar_descarga(archivo_descarga, request_line, gzip_accept and gzip_activo) 
            client_socket.sendall(response_h)           
            T1 = time.perf_counter_ns() # Detenemos el timer 

            print(f"El archivo se descargó en: {T1-T0} nanosegundos") # Registramos el tiempo que tarda entre la recepción de la request y el envío de la respuesta 

            client_socket.close()
            break # Como se ejecutó una descarga, terminamos el ciclo While True para cerrar el socket del servidor

        if metodo == "POST" and modo_upload: # Caso en que el request es para subir un archivo 

            headers, body = request.split("\r\n\r\n", 1) # Separamos la request en headers y body
            body = body.encode()

            for linea in headers.split("\r\n"): # Obtenemos el boundary dentro de los headers para poder separar el contenido del archivo en manejar_carga
                if "boundary=" in linea:
                    boundary = linea.split("boundary=")[1]
                    break

            content_length = 0
            for linea in headers.split("\r\n"): # Obtenemos el Content-Length para saber cuántos bytes recibiremos
                if "Content-Length:" in linea:
                    content_length = int(linea.split(":")[1].strip())
                    break

            while len(body) < content_length: # Se reciben bytes del cliente hasta obtener la longitud completa del body
                body += client_socket.recv(4096)

            # Se procesa el archivo enviado por el cliente con la función manejar_carga
            respuesta = manejar_carga(body, boundary, "archivos_servidor")
            client_socket.sendall(respuesta)
            client_socket.close()
            break # Como se ejecutó una carga, terminamos el ciclo While True para cerrar el socket del servidor
        
        # Si el método o la ruta del request no coincide con ninguno de los casos contemplados, se considera un error
        cuerpo = b"<h1>404 Not Found</h1>"
        response = (
            b"HTTP/1.1 404 Not Found\r\n"
            b"Content-Type: text/html\r\n"
            b"Content-Length: " + str(len(cuerpo)).encode() + b"\r\n"
            b"\r\n"
            + cuerpo
        )

        client_socket.sendall(response)
        client_socket.close()

    server_socket.close() 


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso:")
        print("  python tp.py upload                    # Servidor para subir archivos")
        print("  python tp.py download archivo.txt      # Servidor para descargar un archivo")
        sys.exit(1)
    
    print("ANTES DEL QR")
    imprimir_qr_en_terminal("https://google.com")
    print("DESPUÉS DEL QR")
    comando = sys.argv[1].lower()

    if comando == "upload":
        start_server(archivo_descarga=None, modo_upload=True)

    elif comando == "download" and len(sys.argv) > 2:
        archivo = sys.argv[2]
        ruta_archivo = os.path.join("archivos_servidor", archivo)
        start_server(archivo_descarga=ruta_archivo, modo_upload=False)

    else:
        print("Comando no reconocido o archivo faltante")
        sys.exit(1)