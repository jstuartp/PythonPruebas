import matplotlib.pyplot as plt
from obspy import read

# Cargar el archivo .mseed
file_path = "01-30-2025-14-50-37_MF_PLRL.mseed"  # Reemplaza con la ruta de tu archivo .mseed
stream = read(file_path)

# Configurar la figura y subgráficos
fig, axes = plt.subplots(len(stream), 1, figsize=(12, 8), sharex=True)

nombreEstacion=""

# Graficar cada traza en su respectivo subgráfico
for i, trace in enumerate(stream):
    nombreEstacion=trace.stats.station
    ax = axes[i]
    # Convertir los tiempos a segundos relativos desde el inicio de la traza
    times = trace.times()
    ax.plot(trace.data, label=f"Traza: {trace.id}", color='blue')
    ax.set_ylabel("Amplitud")
    ax.legend(loc="upper right")
    ax.grid(True)
    # Centrar el eje Y en 0 para cada traza


# Etiquetas generales del gráfico
fig.suptitle("Grafica PGA para %s" %nombreEstacion, fontsize=14)
axes[-1].set_xlabel("Tiempo")

# Formato automático de las fechas en el eje X
plt.gcf().autofmt_xdate()

# Guardar el gráfico en un archivo
output_file = "01-30-2025-14-50-37_MF_PLRL.png"
plt.savefig(output_file, dpi=300)

# Mostrar el gráfico en pantalla
plt.show()
plt.close()

print(f"Gráfico guardado exitosamente en {output_file}")