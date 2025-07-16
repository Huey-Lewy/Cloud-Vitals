# dashboard.py
import tkinter as tk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# create window, title and size of window
window = tk.Tk()
window.title("Cloud Vitals Dashboard")
window.geometry("1350x400")

#figure and axis for graphs
def add_graph(title, parent, axisY):
    fig,ax = plt.subplots(figsize=(3,2))
    ax.plot(axisY)
    ax.set_title(title)
    canvas = FigureCanvasTkAgg(fig,master=parent)
    canvas.get_tk_widget().pack()


# Header text for GUI
header = tk.Label(window,text="Welcome to the Cloud Vitals Dashboard!", font=("Arial",16))
header.pack(pady=20)

#create Frames for graphs to go in later
cpuFrame = tk.LabelFrame(window, text="CPU Usage", padx=5, pady=5)
cpuFrame.pack(side="left",padx=10,pady=10)
add_graph("Cpu Usage: ",cpuFrame,10)
#b = tk.Button(cpuFrame,text="cpu")
#b.pack(padx=10,pady=10)

memFrame = tk.LabelFrame(window, text="Memory Usage", padx=5, pady=5)
memFrame.pack(side="left",padx=10,pady=10)
add_graph("Cpu Usage: ",memFrame,10)

#c = tk.Button(memFrame,text="mem")
#c.pack(padx=10,pady=10)

diskFrame = tk.LabelFrame(window, text="Disk Usage", padx=5, pady=5)
diskFrame.pack(side="left",padx=10,pady=10)
add_graph("Cpu Usage: ",diskFrame,10)

#d = tk.Button(diskFrame,text="disk")
#d.pack(padx=10,pady=10)

networkFrame = tk.LabelFrame(window, text="Network Traffic Usage", padx=5, pady=5)
networkFrame.pack(side="left", padx=10,pady=10)
add_graph("Network Traffic Usage: ",networkFrame,10)

#e = tk.Button(networkFrame,text="network")
#e.pack(padx=10,pady=10)

window.mainloop()

"""
Cloud Vitals Dashboard

This script runs on your local machine (or a separate VM).
Periodically checks the Cloud Vital Agents' endpoints using requests,
aggregates the returned data, and renders the resulting data visually. 
"""
