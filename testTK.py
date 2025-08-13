import tkinter as tk

def main():
    root = tk.Tk()
    root.title("Tkinter Test")
    root.geometry("300x150")

    label = tk.Label(root, text="Tkinter is working!", font=("Arial", 14))
    label.pack(pady=20)

    button = tk.Button(root, text="Close", command=root.destroy)
    button.pack(pady=10)

    root.mainloop()

if __name__ == "__main__":
    main()
