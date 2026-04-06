import pandas as pd
import requests
import zipfile
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import os

#   FUNCTIONS
#   getOnePdf(year,id): Downloads the pdf of name id.pdf of the year year and return the headers of that request
#   getAllPdf(year): Downloads all pdf of a year but if it's the current year it starts function getAllActualPdf and terminates
#   getAllActualPdf(): Downloads all pdf of current year and creates Lista_actual.csv ("Name","Date","Error") 
#   getOneZip(year): Downloads the zip of a year and returns the headers of the request
#   getOnePdfHeaders(year,id): Same but not downloading
#   getOneZipHeaders(year): Same but not downloading



importantLinks = ["https://fd.house.gov/reference/asset-type-codes.aspx",                       #Know what each asset refers to
                  "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2025/<id>.pdf",     #Change <id> by a valid id, url to get the PDF
                  "https://disclosures-clerk.house.gov/public_disc/financial-pdfs/<year>FD.zip"   #Change <year> by a valid year, url to get the list of IDs
                  ]


now = datetime.now()

def getOnePdf(year, id):
    url = f"https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{year}/{id}.pdf"
    pathReceived = f"../{year}/movementsPdf/{id}.pdf"

    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()

        with open(pathReceived, "wb") as f:
            f.write(r.content)

        return r.headers

    except requests.exceptions.HTTPError as e:
        log_error(year, f"Error HTTP con ID {id}: {e}")

    except requests.exceptions.RequestException as e:
        log_error(year, f"Error de conexión o timeout con ID {id}: {e}")

    except Exception as e:
        log_error(year, f"Error inesperado con ID {id}: {e}")


def log_error(year, message):
    print(message)
    with open(f"../{year}/errors/errorCurling.txt", "a") as g:
        g.write(message + "\n")


def getAllPdf(year):
    db = pd.read_csv(f"../{year}/{year}FD.txt", sep="\t")
    idAll = db["DocID"]

    os.makedirs(f"../{year}/errors", exist_ok=True)

    with open(f"../{year}/errors/errorCurling.txt", "w") as g:
        g.write("ARCHIVO PARA LOS ERRORES AL DESCARGAR LOS PDF\n")

    # Ajusta max_workers según tu conexión (10-30 suele ir bien)
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(getOnePdf, year, id) for id in idAll]

        for future in as_completed(futures):
            future.result()


def getOneZip(year):
    try:
        r = requests.get(f"https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}FD.zip")
        r.raise_for_status()

        with open(f"../{year}/{year}FD.zip", "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        with zipfile.ZipFile(f"../{year}/{year}FD.zip") as z:
            z.extract(f"{year}FD.txt", path=f"../{year}")

        return r.headers

    except requests.exceptions.HTTPError as e:
        print(f"Error descargando el .zip: {e}")
        with open(f"../{year}/errors/errorCurling.txt","a") as g:
            g.write(f"Error descargando el .zip: {e}\n")

    except requests.exceptions.RequestException as e:
        print(f"Error de conexión o timeout con .zip: {e}")
        with open(f"../{year}/errors/errorCurling.txt","a") as g:
            g.write(f"Error de conexión o timeout con .zip: {e}\n")

    except Exception as e:
        print(f"Error inesperado con .zip: {e}") 
        with open(f"../{year}/errors/errorCurling.txt","a") as g:
            g.write(f"Error inesperado con .zip: {e}\n")

def getAllActualPdf():
    year = now.year

    db = pd.read_csv(f"../{year}/{year}FD.txt", sep="\t")
    idAll = db["DocID"]

    listaActual = pd.DataFrame(columns=["Name", "Date", "Error"])

    #Zip
    try:
        headers_zip = getOneZipHeaders(year)
        fecha_mod = headers_zip.get("last-modified", "")
        
        
        fila_zip = pd.DataFrame([{
            "Name": f"{year}FD.zip", 
            "Date": fecha_mod, 
            "Error": ""
        }])

    except Exception:
        fila_zip = pd.DataFrame([{
            "Name": f"{year}FD.zip", 
            "Date": "", 
            "Error": "Yes"
        }])
    
    listaActual = pd.concat([listaActual, fila_zip], ignore_index=True)

    #Pdf
    for id in idAll:
        try:
            
            headers_pdf = getOnePdf(year, id)
            fecha_mod = headers_pdf.get("last-modified", "")

            nueva_fila = pd.DataFrame([{
                "Name": f"{id}.pdf", 
                "Date": fecha_mod, 
                "Error": ""
            }])

        except Exception:
            
            nueva_fila = pd.DataFrame([{
                "Name": f"{id}.pdf", 
                "Date": "", 
                "Error": "Yes"
            }])

        listaActual = pd.concat([listaActual, nueva_fila], ignore_index=True)

    listaActual.to_csv("../Lista_actual.csv", index=False, encoding='utf-8-sig')

def getOnePdfHeaders(year,id):
    url = f"https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{year}/{id}.pdf"

    try:
        r = requests.head(url)
        print(r.headers.get("last-modified"))
        return r.headers

    except Exception as e:
        print(e)

def getOneZipHeaders(year):
    url = f"https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}FD.zip"

    try:
        r = requests.head(url)
        print(r.headers.get("last-modified"))
        return r.headers

    except Exception as e:
        print(e)


if __name__ == "__main__":
    getAllPdf(2026)
