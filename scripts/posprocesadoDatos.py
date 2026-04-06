import pandas as pd
import yfinance as yf
import numpy as np
import time
import random

def generar_features(input_csv, output_csv):
    print(f"--- Iniciando Feature Engineering sobre {input_csv} ---")
    
    # 1. Cargar datos
    try:
        df = pd.read_csv(input_csv)
    except:
        df = pd.read_csv(input_csv, sep=',', engine='python')

    # Limpieza inicial
    df['Tx_Type'] = df['Tx_Type'].astype(str).str.strip().str.upper()
    df = df[df['Tx_Type'] == 'P'].copy()
    if 'Filing Status' in df.columns:
        df = df[df["Filing Status"] == 'new']

    # Asegurar formato de fechas Y QUITAR ZONAS HORARIAS
    df['Notif_Date'] = pd.to_datetime(df['Notif_Date'], errors='coerce', dayfirst=False).dt.tz_localize(None)
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce', dayfirst=False).dt.tz_localize(None)
    
    df = df.dropna(subset=['Notif_Date', 'Acronym'])
    df['Acronym'] = df['Acronym'].str.strip().str.upper()
    
    # Ordenar cronológicamente
    df = df.sort_values('Notif_Date').reset_index(drop=True)

    # =========================================================================
    # FEATURE 1: SECTOR DE LA EMPRESA (SECUENCIAL CON SIGILO Y REINTENTOS)
    # =========================================================================
    print("\n1. Extrayendo Sectores de Yahoo Finance")
    tickers_unicos = df['Acronym'].unique()
    mapa_sectores = {}
    
    for i, ticker in enumerate(tickers_unicos):
        intentos = 0
        sector_encontrado = 'Desconocido'
        
        while intentos < 3:
            try:
                # Espera aleatoria para no saturar la API
                time.sleep(random.uniform(0.3, 1.0))
                
                info = yf.Ticker(ticker).info
                if not info:
                    raise ValueError("Info vacía")
                
                # Buscar sector o categoría (para ETFs)
                sector = info.get('sector')
                if not sector:
                    sector = info.get('category', 'Desconocido')
                    
                sector_encontrado = sector
                break # Si tiene éxito, salimos del bucle while
                
            except Exception:
                intentos += 1
                time.sleep(2) # Si falla, esperamos 2 segundos antes de reintentar
                
        mapa_sectores[ticker] = sector_encontrado
        
        if (i + 1) % 20 == 0:
            print(f"   Procesados {i + 1}/{len(tickers_unicos)} tickers...")

    df['Sector'] = df['Acronym'].map(mapa_sectores)

    # =========================================================================
    # FEATURE 2: RÉGIMEN DEL S&P 500 (Alcista / Bajista) CORREGIDO
    # =========================================================================
    print("\n2. Calculando Régimen de Mercado (S&P 500 SMA-50)...")
    try:
        spy = yf.download('SPY', start="2021-01-01", progress=False, auto_adjust=True)
        
        # Extracción segura de la columna Close
        if isinstance(spy.columns, pd.MultiIndex):
            spy_close = spy['Close']['SPY'].dropna()
        else:
            spy_close = spy['Close'].dropna()
            
        spy_df = pd.DataFrame({'Close': spy_close})
        
        # QUITAR ZONA HORARIA AL ÍNDICE DE YAHOO (Vital para cruzar fechas)
        spy_df.index = spy_df.index.tz_localize(None)
        
        # Calcular media móvil y tendencia
        spy_df['SMA_50'] = spy_df['Close'].rolling(window=50).mean()
        spy_df['SPY_Trend'] = np.where(spy_df['Close'] > spy_df['SMA_50'], 1.0, 0.0)
        
        # Eliminar nulos generados por los primeros 50 días de la media móvil
        spy_df = spy_df.dropna(subset=['SPY_Trend'])
        spy_df = spy_df.sort_index()

        # Cruce robusto: Busca la fecha más cercana hacia atrás (por si notifica un domingo)
        df = pd.merge_asof(
            df, 
            spy_df[['SPY_Trend']], 
            left_on='Notif_Date', 
            right_index=True, 
            direction='backward'
        )
        
        # Si alguna fecha es anterior a 2021, rellenamos con 0 para evitar nulos
        df['SPY_Trend'] = df['SPY_Trend'].fillna(0.0)
        
        # Imprimir un test rápido para ver que funciona
        positivos = (df['SPY_Trend'] == 1.0).sum()
        print(f"   Test SPY_Trend: {positivos} operaciones en mercado alcista, {len(df)-positivos} en bajista.")

    except Exception as e:
        print(f"Error descargando SPY: {e}")
        df['SPY_Trend'] = 0.0

    # =========================================================================
    # FEATURE 3: ACTIVIDAD RECIENTE DEL SENADOR
    # =========================================================================
    print("\n3. Calculando actividad reciente de cada senador...")
    df['Operaciones_Ultimos_30d'] = 0
    
    for i, row in df.iterrows():
        fecha_actual = row['Notif_Date']
        senador = row['Name']
        fecha_limite = fecha_actual - pd.Timedelta(days=30)
        
        filtro = (df['Name'] == senador) & (df['Notif_Date'] >= fecha_limite) & (df['Notif_Date'] < fecha_actual)
        df.loc[i, 'Operaciones_Ultimos_30d'] = filtro.sum()

    # =========================================================================
    # FEATURE 4: EFECTO MANADA (COMPRADORES RECIENTES DEL MISMO TICKER)
    # =========================================================================
    print("\n4. Calculando el 'Efecto Manada' (Compradores del mismo ticker en 15 días)...")
    df['Compradores_Mismo_Ticker_15d'] = 0
    
    for i, row in df.iterrows():
        fecha_actual = row['Notif_Date']
        ticker = row['Acronym']
        # Ventana de 15 días hacia atrás
        fecha_limite = fecha_actual - pd.Timedelta(days=15)
        
        # Filtramos operaciones del MISMO ticker en esos 15 días previos
        filtro_manada = (df['Acronym'] == ticker) & (df['Notif_Date'] >= fecha_limite) & (df['Notif_Date'] < fecha_actual)
        
        # Contamos cuántos senadores DISTINTOS ('Name') compraron esa acción
        personas_unicas = df.loc[filtro_manada, 'Name'].nunique()
        df.loc[i, 'Compradores_Mismo_Ticker_15d'] = personas_unicas

    # Guardar el CSV enriquecido
    print(f"\nGuardando datos enriquecidos en {output_csv}...")
    df.to_csv(output_csv, index=False)
    print("¡Proceso terminado con éxito!")
    return df

def testing(archivo_csv):
    print(f"\n--- INICIANDO TEST DE VERIFICACIÓN SOBRE: {archivo_csv} ---")
    
    # Cargamos el dataframe que acabamos de generar
    df = archivo_csv

    # Función interna que devuelve los registros 'Desconocidos'
    def obtener_desconocidos(datos):
        # Filtramos donde el sector no se encontró
        df_desc = datos[datos['Sector'] == 'Desconocido']
        # Devolvemos solo los nombres de los tickers únicos (para no imprimir miles de filas repetidas)
        return df_desc['Acronym'].unique()

    # Llamamos a la función interna
    tickers_sin_sector = obtener_desconocidos(df)
    
    # Printeamos los resultados
    cantidad = len(tickers_sin_sector)
    print(f"Total de Tickers únicos sin sector asignado: {cantidad}")
    
    if cantidad > 0:
        print("\nLista de Tickers 'Desconocidos':")
        # Lo imprimimos en forma de lista separada por comas para que sea fácil de leer
        print(", ".join(tickers_sin_sector))
    else:
        print("¡Excelentes noticias! La API encontró el sector para el 100% de los tickers.")

# =========================================================================
# EJECUCIÓN
# =========================================================================
if __name__ == "__main__":
    # CAMBIA ESTAS RUTAS POR LAS TUYAS
    ARCHIVO_ENTRADA = '../2026/2026.csv'          # El que te junta tu 'main'
    ARCHIVO_SALIDA = '../2026PP.csv' # El que leerá tu IA
    
    df = generar_features(ARCHIVO_ENTRADA, ARCHIVO_SALIDA)
    testing(df)
