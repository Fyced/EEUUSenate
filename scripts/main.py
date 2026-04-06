import PdfGetter as gett
import posprocesadoDatos as pp
import extractionv2 as ex
import pandas as pd
from pathlib import Path
import shutil  
from datetime import datetime
import os
import requests
import re

def main():
    #creationStructure(2026,2026)
    #gett.getOnePdfHeaders(2025,30025433)
    concatAllCsv(2020,2025)
    #getAndExtract()
    #testing()
    pp.generar_features('../2020-2025.csv','../2020-2025PP.csv')

   
    
def testing():
    dataset = pd.read_csv("../2018-2026.csv")
    print("Iniciando Testing")
    def filasSinAmount():
        cols = dataset["Amount"].astype(str).str.strip().replace("nan",pd.NA)
        ds = dataset[cols.isna() | (cols == "")]
        
        return ds

    def filasStockSinAcronym():
        #Es posible que salgan filas que no se ha cogido el acronym porque son stocks con preferencia([A-Z]+$[A_Z]). No las analizaremos
        ds = dataset[
            dataset["Acronym"].isna() &
            (
                (dataset["Op_Type"] == "ST") |
                (dataset["Op_Type"] == "OP")
            )
        ]
        return ds


    def filasSinOptype():
        #Suelen ser datos basura. Hay que eliminar esos datos
        ds = dataset[
            (dataset["Acronym"].isna() | (dataset["Acronym"] == "")) &
            (dataset["Op_Type"].isna() | (dataset["Op_Type"] == ""))
        ]
        return ds
    
    def filasSinFechas():
        #Deberia ser 0
        ds = dataset[
            (dataset["Date"].isna() | dataset["Date"] == "") &
            (dataset["Notif_Date"].isna() | dataset["Notif_Date"] == "")
        ]
        return ds
    
    def filasFechaDefectuosa():
        #Deberia ser 0
        ds = dataset[
            (dataset["Notif_Date"].astype(str).str.len() != 10) |
            (dataset["Date"].astype(str).str.len() != 10) |
            (~dataset["Date"].astype(str).str.match(r'^\d{1,2}/\d{1,2}/\d{4}$')) |
            (~dataset["Notif_Date"].astype(str).str.match(r'^\d{1,2}/\d{1,2}/\d{4}$'))
        ]
        return ds
    
    def filasSinFS():
        #
        ds = dataset[dataset['Filing Status'] == 'O']
        return ds
    
    def filasNew():
        #
        ds = dataset[dataset['Filing Status'].str.lower().str.strip() == 'new']
        return ds
    
    def filasAcronymUsable():
        #
        patron = r'^[A-Z]+$'
        ds = dataset[dataset['Acronym'].str.contains(patron, na=False, regex=True)]
        return ds

    print("-"*45)
    print("Filas sin Amount:")
    print(filasSinAmount())

    print("-"*45)
    print("Filas de Stocks sin Acronym:")
    print(filasStockSinAcronym())

    print("-"*45)
    print("Filas sin Op Type y sin Acronym:")
    print(filasSinOptype())

    print("-"*45)
    print("Filas sin fechas:")
    print(filasSinFechas())

    print("-"*45)
    print("Filas con fecha defectuosa:")
    print(filasFechaDefectuosa())

    print("-"*45)
    print("Filas sin Filing Status:")
    print(filasSinFS())

    print("-"*45)
    print("Filas con Filing Status: new")
    print(filasNew())

    print("-"*45)
    print("Filas con Acronym aceptable")
    print(filasAcronymUsable())


def creationStructure(yearMin, yearMax):
    os.makedirs("../data",exist_ok=True)
    os.makedirs(f"../errorsGlobal",exist_ok=True)

    for year in range(yearMin, yearMax+1):
        os.makedirs(f"../{year}/errors",exist_ok=True)
        os.makedirs(f"../{year}/movementsPdf",exist_ok=True)

        if not os.path.exists(f"../{year}/errors/errorCurling.txt"):
            with open(f"../{year}/errors/errorCurling.txt", "w", encoding="utf-8") as f:
                pass  # Crea el archivo

        gett.getOneZip(year)
    

def getAndExtract():
    yearMin = input("Until what year you want to extract?")
    #yearMax = datetime.now().year
    yearMax = 2025
    test = False

    if not yearMin:
        yearMin = 2018
    elif yearMin == "t":
        yearMax = 0
        yearMin = 0
        test = True
    else:
        yearMin = int(yearMin)

    #Obsolete?
    #if not test:
    #    creationStructure(yearMin=yearMin, yearMax=yearMax)

    try:
        with open("../errorsGlobal/erroresExtractAño.txt","w") as f:
            f.write(f"ARCHIVO PARA CONTAR CUANTOS ERRORES DE EXTRACCION HAN HABIDO POR CADA AÑO\n")

        with open(f"../errorsGlobal/erroresNoTratados.txt","w") as f:
            f.write("ARCHIVO PARA SABER LOS ERRORES QUE NO SE HAN CONTEMPLADO POR OTROS ARCHIVOS\n")
        
        if not test: 
            ahora = datetime.now()
            with open("../errorsGlobal/erroresNoTratadosHistorico.txt", "a", encoding="utf-8") as f:
                f.write(f"\n\n\n\t\tFecha: {ahora.strftime('%d/%m/%Y %H:%M:%S')}. ")
    except Exception as e:
        print(e)
        return 0

    errorAcum = 0  #Numero de errores al extraer la info de los pdf(Contamos como error el que no detecte el texto)
    for year in range(yearMin,yearMax+1):
        print(f"Starting with year {year}")
        print("-"*45)

        #gett.getAllPdf(year)
        #contar_pdfs_improcesables(year)
        #mover_pdfs_improcesables(year)
        error = ex.extraction(year,test=test)

        errorAcum += error
        try:
            with open("../erroresExtractAño.txt","a") as f:
                f.write(f"{year}: {error}\n")
        except Exception as e:
            print(f"Error abriendo erroresExtractAño: {e}")

    if not test:
        try:
            concatAllCsv(yearMin,yearMax)
            with open("../erroresNoTratados.txt", "r", encoding="utf-8") as f_origen, \
                open("../erroresNoTratadosHistorico.txt", "a", encoding="utf-8") as f_destino:
                primera = True
                f_destino.write(f"Interval {yearMin}-{yearMax}: {errorAcum}\n")
                for linea in f_origen:      #Copiar los errores de esta ejecucion quitando la primera linea(es el header del archivo anterior)
                    if primera:
                        primera = False
                        continue
                    f_destino.write(linea)
        except Exception as e:
            print("Error on last part: {e}")

def concatAllCsv(yearMin,yearMax,test = False):
        fout = []
        path = "../testPdf"
        pathOutput = f"../{yearMin}-{yearMax}.csv"
        for year in range(yearMin,yearMax+1):
            if not test:
                path = f"../{year}"
            csv = pd.read_csv(f"{path}/{year}.csv")
            fout.append(csv)
        listAllCsv = pd.concat(fout,ignore_index=True)
        listAllCsv.to_csv(pathOutput,index=False,encoding="utf-8-sig")
        print("-"*30)
        print(f"Csv in range {yearMin}-{yearMax} have been merged")

def mover_pdfs_improcesables(year):
    directorio = f"../{year}/movementsPdf"    #Directorio donde busca los PDF, y creara la carpeta nueva
    origen = Path(directorio)
    
    if not origen.exists():
        print("Error: El directorio indicado no existe.")
        return

    #Definimos la carpeta destino y la creamos
    destino = origen / "improcesables"             #El operador '/' une rutas de forma inteligente
    
    #'exist_ok=True' evita errores si la carpeta ya existe
    destino.mkdir(exist_ok=True) 
    print(f"Carpeta destino preparada: {destino}")

    #Buscamos los pdf (empiezan por 8 o 9)
    archivos_a_mover = list(origen.glob('[89]*.pdf'))
    
    if not archivos_a_mover:
        print("No se encontraron archivos que cumplan la condición.")
        return

    contador = 0
    for archivo in archivos_a_mover:
        try:
            #Construimos la ruta final (destino + nombre del archivo)
            ruta_final = destino / archivo.name
            
            #Movemos el archivo
            shutil.move(str(archivo), str(ruta_final))
            print(f"Movido: {archivo.name}")
            contador += 1
        except Exception as e:
            print(f"Error al mover {archivo.name}: {e}")

    print("-" * 30)
    print(f"Proceso finalizado. Se movieron {contador} archivos a 'improcesables'.")
    
def contar_pdfs_improcesables(year):
    origen = Path(f"../{year}/movementsPdf")
    archivosMover = list(origen.glob('[89]*.pdf'))
    numArchMov = len(archivosMover)

    print("-"*30)
    print(f"Hay {numArchMov} archivos improcesables")
    
if __name__ == "__main__":
    main()