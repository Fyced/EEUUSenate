import pdfplumber
import pandas as pd
import re
import glob
import os

#!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
#EN 2017 NO HAY [], ACABAN POR (), HACER QUE SI NO ENCUENTRA [] COJA COMO ULTIMA PARTE DEL ASSET ACRONYM. TAMBIEN COGE MAL LOS DATOS EN GENERAL

def extraction(year,test = False):
    #Rutas de input y output
    path = f"../{year}"
    directorio_pdfs = f"{path}/movementsPdf"  # Carpeta de los PDF
    nombre_salida = f"{path}/{year}.csv"

    if test == True:
        path = "../testPdf"
        directorio_pdfs = f"{path}"
        nombre_salida = f"{path}/t.csv"
    
    os.makedirs(f"{path}/errors",exist_ok=True)

    with open(f"{path}/errors/erroresExtraction.txt","w") as f:
        f.write("ARCHIVO PARA SABER LOS ERRORES EN LA EXTRACCION DE DATOS\n")

    with open(f"{path}/errors/errorFechas.txt","w") as g:
        g.write("ARCHIVO PARA SABER QUE ARCHIVOS TIENEN MAL ALGUNA FECHA\n")
    
    with open(f"{path}/errors/errorAmount.txt","w") as g:
        g.write(f"ARCHIVO PARA CONTAR LAS VECES QUE HAY TEXTO ANOMALO EN LA COLUMNA AMOUNT\n")


    #Rangos de dinero que pueden haber en la columna amount.
    RANGOS_OFICIALES = {
        "$1,001": "$1,001 - $15,000",
        "$15,001": "$15,001 - $50,000",
        "$50,001": "$50,001 - $100,000",
        "$100,001": "$100,001 - $250,000",
        "$250,001": "$250,001 - $500,000",
        "$500,001": "$500,001 - $1,000,000",
        "$1,000,001": "$1,000,001 - $5,000,000",
        "$5,000,001": "$5,000,001 - $25,000,000",
        "$25,000,001": "$25,000,001 - $50,000,000",
        "$50,000,001": "$50,000,001 +",
    }

    RANGOS_OFICIALES_NUM = {
        "$1,001 - $15,000": 7500,
        "$15,001 - $50,000": 32500,
        "$50,001 - $100,000": 75000,
        "$100,001 - $250,000": 175000,
        "$250,001 - $500,000": 375000,
        "$500,001 - $1,000,000": 750000,
        "$1,000,001 - $5,000,000": 3000000,
        "$5,000,001 - $25,000,000": 15000000,
        "$25,000,001 - $50,000,000": 37500000,
        "$50,000,001 +": 50000000,
    }

    patronOpType = r'\[([A-Z]+)\]'
    patronAcronym = r'\(([A-Z]+)(?:\.([A-Z]+))?\)'
    patronFS = r"F.*?S.*?:\s*(new|amended|deleted)"

    #Lista acumuladora
    lista_dataframes = []

    #Numero de errores(Pdf sobre los que no se ha detectado toda la info)
    errorCount = 0

    #Buscamos todos los archivos .pdf
    archivos_encontrados = glob.glob(os.path.join(directorio_pdfs, "*.pdf"))
    print("-"*45)
    print(f"Se han encontrado {len(archivos_encontrados)} archivos PDF.")

    #Bucle por cada archivo
    for archivo in archivos_encontrados:
        nombre_archivo = os.path.basename(archivo)
        print(f"\nProcesando: {nombre_archivo}... \tYear: {year}")

        try:
            with pdfplumber.open(archivo) as pdf:
                interrupted = False     #variable que indica si un movimiento tiene info en la pagina siguiente
                #Bucle por cada pagina del PDF
                for i, page in enumerate(pdf.pages):
                    registro_temporal = {}
                    print(f"   -> Pág {i+1}...", end="")
                    if i == 0:
                        def extractName():
                            patron = r"Name:\s+(.+)"

                            texto = page.extract_text()
                            if texto:
                                for line in texto.split("\n"):
                                    match = re.search(patron,line,re.IGNORECASE)
                                    if match:
                                        return match.group(1).strip()
                                    
                        name = extractName()
                        if not name:
                            errorCount += 1
                            with open(f"{path}/errors/erroresExtraction.txt","a") as f:
                                f.write(f"No name in archive {nombre_archivo}")


                    header_search = page.search("Asset",case=False) #Como searchAsset
                    searchOwner = page.search("Owner",case=False)
                    searchDate = page.search("Date",case=False)
                    searchTx = page.search("Transaction",case=False)
                    searchNotifDate= page.search("Notification",case=False)
                    searchAmount = page.search("Amount",case=False)
                    searchCap = page.search("Cap.",case=False)
                    

                    if header_search and searchOwner and searchDate and searchTx and searchAmount and searchNotifDate:

                        alturaHeader = searchAmount[0]['top']-5   #Altura a la que estan las palabras del header (se ha tomado con la altura de Amount)
                        
                        if searchCap and (min(searchCap,key= lambda e: abs(e["top"]-alturaHeader))['top'] >= alturaHeader-5 and min(searchCap,key= lambda e: abs(e["top"]-alturaHeader))['top'] <= alturaHeader+5):
                            limitAmountXDistance = min(searchCap,key= lambda e: abs(e["top"]-alturaHeader))['x0']-5
                        else:
                            limitAmountXDistance = searchAmount[0]['x0']+100

                        #Lo que hace esto es coger el elemento de la lista de posibles headers que mas se acerque al de altura header
                        lineas_corte = [min(searchOwner,key= lambda e: abs(e["top"]-alturaHeader))['x0']-5,                                         #Owner
                                            min(header_search,key= lambda e: abs(e["top"]-alturaHeader))['x0'] - 7,                                 #Asset
                                               min(searchTx,key= lambda e: abs(e["top"]-alturaHeader))['x0']-5,                                     #Transaction Type
                                                   min(searchDate,key= lambda e: abs(e["top"]-alturaHeader))['x0']-5,                              #Date
                                                        min(searchNotifDate,key= lambda e: abs(e["top"]-alturaHeader))['x0']-1,                     #Notif Date
                                                            searchAmount[0]['x0']-3,                                                                #Amount
                                                                limitAmountXDistance, page.width]                                                   #Cap.   (solo para tener el limite)                                          
                        #lineas_corte = [85, 105, 263, 320, 382, 445, 560, page.width]
                        #                Owner aset Tx  date  notif amount
                        # Owner = 84-117        62-95
                        # Asset = 123-149       101-128
                        # Tx = 269-327          246-307
                        # Date                  312-335
                        # NotifDate = 389-448   364-424
                        # Amount = 454-493      429-470

                        top_y = alturaHeader
                        crop_box = (0, top_y, page.width, page.height)
                        cropped_page = page.crop(crop_box)
                        
                        #Settings que usara para determinar las columnas y coger la info
                        settings = {
                            "vertical_strategy": "explicit",
                            "explicit_vertical_lines": lineas_corte,
                            "horizontal_strategy": "text", 
                            "text_y_tolerance": 5,
                            "intersection_x_tolerance": 40
                        }

                        #Debuggear una pagina
                        def debugCroppedPage():
                            # Crea una imagen visual de cómo pdfplumber está entendiendo tu configuración
                            im = cropped_page.to_image(resolution=150)

                            # Dibuja las líneas verticales que has calculado (en rojo)
                            im.debug_tablefinder(settings)

                            # Guarda o muestra la imagen para inspeccionarla
                            im.save("debugPage.png")
                        
                        if nombre_archivo == "20023082.pdf" and i+1 == 1:
                            debugCroppedPage()
                        table = cropped_page.extract_table(settings)


                        if table:
                            df = pd.DataFrame(table)
                            df.columns = [f"Col_{j}" for j in range(len(df.columns))]
                            
                            transacciones = []
                            registro_actual = None
                            patron_fecha = r'^\d{1,2}/\d{1,2}/\d{4}$'

                            tempAsset = ""
                            
                            # Reconstrucción
                            for fila in df.to_dict('records'):
                                # Aseguramos que existan columnas suficientes
                                if len(df.columns) < 6: 
                                    errorCount += 1
                                    with open(f"{path}/errors/erroresExtraction.txt","a") as f:
                                        f.write(f"{year}. No suficientes columnas: {df.columns} en {nombre_archivo} page {i+1}\n")

                                # --- MODIFICACIÓN AQUÍ PARA DETECTAR LA FECHA ---
                                # Extraemos los valores crudos
                                val_0 = str(fila.get("Col_0","")).strip()
                                val_1 = str(fila.get("Col_1", "")).strip()
                                #print(val_0)
                                val_2 = str(fila.get("Col_2", "")).strip()
                                #print(val_1)
                                val_3 = str(fila.get("Col_3", "")).strip()
                                #print(val_2)
                                val_4 = str(fila.get("Col_4", "")).strip()
                                #print(val_3)
                                val_5 = str(fila.get("Col_5", "")).strip()
                                #print(val_4)
                                
                                # Buscamos dónde está la fecha realmente (puede haberse movido)
                                fecha_encontrada = None
                                columna_fecha_usada = -1

                                if re.search(patron_fecha, val_3):
                                    fecha_encontrada = val_3
                                    columna_fecha_usada = 3
                                elif re.search(patron_fecha, val_2): # A veces se mueve a la izquierda
                                    fecha_encontrada = val_2
                                    columna_fecha_usada = 2
                                elif re.search(patron_fecha, val_4): # A veces a la derecha
                                    fecha_encontrada = val_4
                                    columna_fecha_usada = 4
                                
                                # Asignamos variables basándonos en donde encontramos la fecha
                                # Si no encontramos fecha, asumimos estructura estándar para acumular texto
                                if fecha_encontrada:
                                    txt_owner = val_0
                                    txt_asset = val_1 # Asset siempre es Col_1 en nuestro corte
                                    txt_type = val_2 if columna_fecha_usada == 3 else "" # Tipo suele estar antes de fecha
                                    txt_date = fecha_encontrada
                                    txt_notif = val_4 if columna_fecha_usada == 3 else ""
                                    txt_amount = val_5 # Amount suele ser Col_5
                                else:
                                    # Si es línea de continuación, usamos los índices fijos estándar
                                    txt_owner = ""
                                    txt_asset = val_1
                                    txt_type = ""
                                    txt_date = "" # No hay fecha
                                    txt_notif = ""
                                    txt_amount = val_5

                                # --- FIN MODIFICACIÓN ---
                                
                                # Lógica de Unión
                                if fecha_encontrada: # Nueva transacción
                                    if registro_actual:
                                        transacciones.append(registro_actual)
                                    registro_actual = {
                                        "Owner": txt_owner.upper(),
                                        "Asset": txt_asset,
                                        "Tx_Type": txt_type.upper(),
                                        "Date": txt_date,
                                        "Notif_Date": txt_notif,
                                        "Amount": txt_amount,
                                        "Filing Status": "O"
                                    }
                                    interrupted = False
                                    registro_temporal = {}
                                    tempAsset = ""
                                elif registro_actual : # Continuación
                                    if val_2:
                                        continue
                                    if txt_asset:
                                        match = re.search(patronFS, txt_asset, re.IGNORECASE)
                                        if match:
                                            registro_actual["Filing Status"] = match.group(1).lower()
                                            continue
                                        registro_actual["Asset"] += " " + txt_asset
                                    if txt_amount:
                                        registro_actual["Amount"] += " " + txt_amount
                                elif val_1 and interrupted == True and (not val_2):
                                    match = re.search(patronOpType,val_1, flags=re.IGNORECASE)
                                    tempAsset += " " + txt_asset
                                    if match:
                                        df_temporal = lista_dataframes[-1]
                                        fila_temporal = df_temporal.iloc[-1].copy()
                                        lista_dataframes[-1] = df_temporal[:-1]

                                        registro_temporal = {
                                            "Owner": fila_temporal["Owner"],
                                            "Asset": fila_temporal["Asset"]+tempAsset,
                                            "Tx_Type": fila_temporal["Tx_Type"],
                                            "Date": fila_temporal["Date"],
                                            "Notif_Date": fila_temporal["Notif_Date"],
                                            "Amount": fila_temporal["Amount"] + txt_amount,
                                            "Filing Status": "O"
                                        }
                                    else:
                                        match = re.search(patronFS, txt_asset, re.IGNORECASE)
                                        if match:
                                            interrupted = False
                                            df_temporal = lista_dataframes[-1]
                                            fila_temporal = df_temporal.iloc[-1].copy()
                                            lista_dataframes[-1] = df_temporal[:-1]

                                            registro_temporal = {
                                                "Owner": fila_temporal["Owner"],
                                                "Asset": fila_temporal["Asset"]+tempAsset,
                                                "Tx_Type": fila_temporal["Tx_Type"],
                                                "Date": fila_temporal["Date"],
                                                "Notif_Date": fila_temporal["Notif_Date"],
                                                "Amount": fila_temporal["Amount"] + txt_amount,
                                                "Filing Status": match.group(1).lower()
                                            }
                                            transacciones.append(registro_temporal)
                            if registro_actual:
                                transacciones.append(registro_actual)
                            
                            # --- LIMPIEZA Y EXTRACCIÓN DE NUEVAS COLUMNAS ---
                            if transacciones:

                                for e in range(0,len(transacciones)):
                                    match = re.search(patronFS, txt_asset, re.IGNORECASE)
                                    #match = re.search(patronOpType,transacciones[e]["Asset"], flags=re.IGNORECASE)
                                    if not match:
                                        if e == len(transacciones)-1:
                                            interrupted = True
                                        elif year > 2018:
                                            errorCount += 1
                                            with open(f"{path}/errors/erroresExtraction.txt","a") as f:
                                                f.write(f"{nombre_archivo}-Sin Op_Type. Page : {i+1}. Last transaction of page: {e == len(transacciones)-1}\n")

                                df_pag = pd.DataFrame(transacciones)
                                
                                #Extracción de ACRONYM (Todo entre mayusculas) (No tiene porque haber)
                                def extract_acronym(texto):
                                    if not isinstance(texto, str): return ""
                                    #Busca (TEXTO) donde TEXTO sean solo letras A-Z mayúsculas
                                    match = re.search(patronAcronym, texto, flags= re.IGNORECASE)
                                    if match:
                                        return match.group(1).upper()
                                    return ""

                                #Extracción de OP_TYPE (Lo que sea entre corchetes)
                                def extract_op_type(texto):
                                    if not isinstance(texto, str): return ""
                                    # Busca [TEXTO]
                                    match = re.search(patronOpType, texto, flags= re.IGNORECASE)
                                    if match:
                                        return match.group(1).upper()
                                    return ""

                                #Limpieza del ASSET
                                def limpiar_texto_asset(texto):
                                    texto = texto.replace('\n', ' ')
                                    texto = re.sub(r'^(SP|JT|DC)\s+', '', texto)
                                    # Cortar en el último corchete ] para limpiar basura final
                                    if "]" in texto:
                                        indice_corte = texto.rfind("]") + 1
                                        texto = texto[:indice_corte]
                                    elif ")" in texto: 
                                        indice_corte = texto.rfind(")") + 1
                                        texto = texto[:indice_corte]
                                    return texto.strip()

                                #Limpieza de AMOUNT 
                                def limpiar_texto_amount(texto):
                                    texto = texto.replace('\n', ' ')
                                    match = re.search(r'\$[\d,]+(?:\.\d{1,2})?', texto)
                                    if match:
                                        primer_numero = match.group(0)
                                        if primer_numero in RANGOS_OFICIALES:
                                            return RANGOS_OFICIALES[primer_numero]
                                        todos_montos = re.findall(r'\$[\d,]+', texto)
                                        if len(todos_montos) >= 2:
                                            return f"{todos_montos[0]} - {todos_montos[1]}"
                                        #A partir de aqui es si hay algo raro en el amount (Texto aclarativo por ejemplo)
                                        if primer_numero != texto:      #Esto es para eliminar el caso de que haya una cantidad exacta (ejemplo: $932.14)
                                            with open(f"{path}/errors/errorAmount.txt","a") as g:
                                                    g.write(f"Texto anomalo en amount. Archivo {nombre_archivo}. {texto}\n")
                                        return texto
                                    return ""
                                
                                def diferenciaFechas(df):
                                    #Revisar parte de Nueva Date
                                    date = pd.to_datetime(df["Date"], dayfirst=False, format="mixed")
                                    notifDate = pd.to_datetime(df["Notif_Date"], dayfirst=False, format="mixed")
                                    diferencia = notifDate-date
                                    if diferencia < pd.Timedelta(0):
                                        if abs(diferencia) <= pd.Timedelta(days=50):
                                            df["Notif_Date"] = date
                                            df["Date"] = notifDate
                                            diferencia = abs(diferencia)
                                            df["Notif_Date"] = notifDate.strftime('%d/%m/%Y')
                                            df["Date"] = date.strftime('%d/%m/%Y')
                                            #with open(f"{path}/errors/errorFechas.txt","a") as g:
                                            #    g.write(f"Error en diferencia de fechas. Archivo {nombre_archivo}. Nueva notifD: Intercambio\n {df}\n")
                                        elif abs(diferencia) <= pd.Timedelta(days=370):
                                            notifDate += pd.Timedelta(days=365)
                                            diferencia = notifDate-date
                                            with open(f"{path}/errors/errorFechas.txt","a") as g:
                                                g.write(f"Error en diferencia de fechas1. Archivo {nombre_archivo}. Nueva notifD: {notifDate}\n {df}\n")
                                            df["Notif_Date"] = notifDate.strftime('%d/%m/%Y')
                                        else:
                                            notifDate = notifDate.replace(year=date.year)
                                            diferencia = notifDate-date
                                            if diferencia < pd.Timedelta(0):
                                                notifDate += pd.Timedelta(days=365)
                                                diferencia = notifDate-date
                                            with open(f"{path}/errors/errorFechas.txt","a") as g:
                                                g.write(f"Error en diferencia de fechas2. Archivo {nombre_archivo}. Nueva notifD: {notifDate}\n {df}\n")
                                            df["Notif_Date"] = notifDate.strftime('%d/%m/%Y')
                                    elif diferencia >= pd.Timedelta(days=365):
                                        date = date.replace(year=notifDate.year)
                                        diferencia = notifDate-date
                                        if diferencia < pd.Timedelta(0):
                                            date -= pd.Timedelta(days=365)
                                            diferencia = notifDate-date
                                        with open(f"{path}/errors/errorFechas.txt","a") as g:
                                            g.write(f"Error en diferencia de fechas. Archivo {nombre_archivo}. Nueva Date: {date}\n {df}\n")
                                        df["Date"] = date.strftime('%d/%m/%Y')
                                    df["Diferencia_Dias"] = diferencia.days
                                    return df

                                def changeDate(text):
                                    #Formato: mm/dd/yyyy -> dd/mm/yyyy
                                    temp = text[:2]
                                    newText = text[3:6]+temp+text[5:]
                                    return newText
                                
                                def formatoDate(Date):
                                    date = Date
                                    if date[2] != '/':
                                        newDate = '0'+date
                                        date = newDate
                                    if date[5] != '/':
                                        newDate = date[:3]+'0'+date[3:]
                                        date = newDate
                                    return date

                                def depurarDate(fila):
                                    date = fila["Date"]
                                    if len(date) > 10:
                                        residuo = date[11:]
                                        newDate = date[:11]
                                        newNotifDate = residuo.replace(' ','') + fila["Notif_Date"]
                                        fila["Date"] = newDate
                                        fila["Notif_Date"] = newNotifDate
                                    return fila
                                
                                def columnaAmountNumeric(amount):
                                    # 1. Si coincide exactamente con el texto de tu diccionario
                                    if amount in RANGOS_OFICIALES_NUM:
                                        return float(RANGOS_OFICIALES_NUM[amount])
                                    
                                    # 2. Si es una cantidad exacta, la limpiamos, evaluamos dónde cae y devolvemos la media del rango
                                    try:
                                        # Quitamos el $, las comas y los espacios
                                        val_limpio = str(amount).replace('$', '').replace(',', '').strip()
                                        val = float(val_limpio)
                                        
                                        # Evaluamos a qué rango pertenece tu cantidad exacta
                                        if val <= 15000:
                                            return 7500.0
                                        elif val <= 50000:
                                            return 32500.0
                                        elif val <= 100000:
                                            return 75000.0
                                        elif val <= 250000:
                                            return 175000.0
                                        elif val <= 500000:
                                            return 375000.0
                                        elif val <= 1000000:
                                            return 750000.0
                                        elif val <= 5000000:
                                            return 3000000.0
                                        elif val <= 25000000:
                                            return 15000000.0
                                        elif val <= 50000000:
                                            return 37500000.0
                                        else:
                                            # Si es más de 50 millones
                                            return 50000000.0
                                            
                                    except ValueError:
                                        # Si el PDF tenía un error de lectura y el texto no es un número
                                        return None

                                
                                # --- APLICAMOS LAS FUNCIONES ---
                                
                                # Primero extraemos los datos nuevos del Asset "sucio" original
                                df_pag["Acronym"] = df_pag["Asset"].apply(extract_acronym)
                                df_pag["Op_Type"] = df_pag["Asset"].apply(extract_op_type)
                                
                                # Luego limpiamos el Asset y el Amount
                                df_pag["Asset"] = df_pag["Asset"].apply(limpiar_texto_asset)
                                df_pag["Amount"] = df_pag["Amount"].apply(limpiar_texto_amount)

                                #Añadimos una columna para el id de quien hizo la operacion
                                separadorId = nombre_archivo.split(".")
                                df_pag["Pdf_Id"] = separadorId[0]

                                #Damos el formato de dd/mm/yyyy (nos aseguramos de que sean 2/2/4)
                                df_pag["Date"] = df_pag["Date"].apply(formatoDate)
                                df_pag["Notif_Date"] = df_pag["Notif_Date"].apply(formatoDate)

                                #Completamos la notif date con el residuo de la date (solo si hay residuo)
                                df_pag = df_pag.apply(depurarDate,axis=1)

                                #Pasamos la fecha a fecha no americana (dd/mm/yyyy)
                                #df_pag["Date"] = df_pag["Date"].apply(changeDate)
                                #df_pag["Notif_Date"] = df_pag["Notif_Date"].apply(changeDate)

                                #Añadimos una columna para la diferencia de dias entre la date y la Notification date
                                df_pag = df_pag.apply(diferenciaFechas,axis=1)

                                #Añadimos una columna para el amount en formato numerico (la media entre los valores del rango)
                                df_pag["Amount_Num"] = df_pag["Amount"].apply(columnaAmountNumeric)

                                #Añadimos una columna para el nombre de la persona 
                                df_pag["Name"] = name

                                #Seleccionamos columnas (Orden en el que apareceran las columnas)       
                                cols = ["Pdf_Id","Owner", "Asset", "Acronym", "Op_Type", "Tx_Type", "Date", "Notif_Date", "Diferencia_Dias", "Amount", "Amount_Num", "Name", "Filing Status"]
                                df_pag = df_pag[cols]

                                #Añadimos a la lista global
                                lista_dataframes.append(df_pag)
                                print(f" {len(df_pag)} filas.")
                            else:
                                print(" 0 filas.")
                                if i < len(pdf.pages)-1 or len(pdf.pages)==1:
                                    errorCount += 1
                                    with open(f"{path}/errors/erroresExtraction.txt","a") as f:
                                        f.write(f"{nombre_archivo}-(0 filas) Page : {i+1}\n")
                        else:
                            print(" Sin tabla.")
                            if i < len(pdf.pages)-1 or len(pdf.pages)==1:
                                errorCount += 1
                                with open(f"{path}/errors/erroresExtraction.txt","a") as f:
                                    f.write(f"{nombre_archivo}-(Sin tabla) Page : {i+1}\n")
                    else:
                        print(" (Sin cabecera)")
                        if i < len(pdf.pages)-1 or len(pdf.pages)==1:
                            errorCount += 1
                            with open(f"{path}/errors/erroresExtraction.txt","a") as f:
                                f.write(f"{nombre_archivo}-(Sin cabecera) Page : {i+1}\n")
                        
        except Exception as e:
            print(f"Error en {nombre_archivo}: {e}")
            errorCount += 1
            with open(f"../errorsGlobal/erroresNoTratados.txt","a") as g:
                g.write(f"{year}. Error en {nombre_archivo}: {e}\n")

    # --- PROCESO FINAL ---
    if lista_dataframes:
        print("\nUnificando todos los datos...")
        df_final_total = pd.concat(lista_dataframes, ignore_index=True)
        
        df_final_total.to_csv(nombre_salida, index=False, encoding='utf-8-sig')
        
        print("-" * 60)
        print("EXTRACCIÓN COMPLETADA")
        print(f"Guardado en: {nombre_salida}")
        print(f"Total filas: {len(df_final_total)}")
        print("-" * 60)
        print(df_final_total)
    else:
        print("No se encontraron datos")
    
    return errorCount       #Returneamos el numero de pdf con fallo en la extraccion en ese año


def extractName(page):
    patron = r"Name:\s+(.+)"

    texto = page.extract_text()
    if texto:
        for line in texto.split("\n"):
            match = re.search(patron,line)
            if match:
                return match.group(1).strip()


if __name__ == "__main__":
    extraction(2026)