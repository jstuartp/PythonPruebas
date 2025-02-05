import matplotlib.pyplot as plt
from obspy import read

# Cargar el archivo .mseed
file_path = "01-30-2025-14-50-37_MF_PLRL.mseed"  # Reemplaza con la ruta de tu archivo .mseed
stream = read(file_path)

stream.plot(title="Titulo",size=(1000,600),color="blue",outfile="01-30-2025-14-50-37_MF_PLRL.png",show="true") #PLOTEO DE IMAGEN y se guarda el archivo

# Guardar el gráfico en un archivo
#output_file = "01-30-2025-14-50-37_MF_PLRL.png"
#plt.savefig(output_file, dpi=300)

# Mostrar el gráfico en pantalla
#plt.show()

print(f"Gráfico guardado exitosamente ")