"""
2D Inequality / Equation Visualizer
=====================================
Visualize expressions in x and y up to 2nd order.

Created on Jan 15 2022

Last updated on Jun 24 2026

@author: Augustin Guibaud, cleaned with Claude
"""

import tkinter as tk
from tkinter import ttk, messagebox
import numpy as np
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.colors import ListedColormap
import re


# ---------------------------------------------------------------------------
# Safe expression evaluator (x, y only, 2nd order terms allowed)
# ---------------------------------------------------------------------------

ALLOWED_NAMES = {
    "x": None, "y": None,
    "sin": np.sin, "cos": np.cos, "tan": np.tan,
    "exp": np.exp, "log": np.log, "log10": np.log10,
    "sqrt": np.sqrt, "abs": np.abs,
    "pi": np.pi, "e": np.e,
}

def safe_eval_expr(expr_str: str, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Evaluate a math expression string over numpy arrays x, y."""
    # Replace ^ with ** for convenience
    expr_str = expr_str.replace("^", "**")
    # Build safe namespace
    ns = {k: v for k, v in ALLOWED_NAMES.items()}
    ns["x"] = x
    ns["y"] = y
    # Block any dunder / import attempts
    if any(kw in expr_str for kw in ["__", "import", "open", "exec", "eval"]):
        raise ValueError("Unsafe expression detected.")
    return eval(compile(expr_str, "<string>", "eval"), {"__builtins__": {}}, ns)  # noqa: S307


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------

class InequalityVisualizer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("2D Inequality / Equation Visualizer")
        self.resizable(True, True)
        self.configure(bg="#f5f5f5")

        self._build_control_panel()
        self._build_plot_panel()

        # Initial plot with the example from the paper
        self.expr_var.set("-0.57975 + 1.51*x + 3.215*y*(x-1)")
        self.relation_var.set(">0")
        self.x_min_var.set("-4")
        self.x_max_var.set("4")
        self.y_min_var.set("-4")
        self.y_max_var.set("4")
        self.resolution_var.set("400")
        self._plot()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_control_panel(self):
        ctrl = tk.Frame(self, bg="#f0f0f0", padx=12, pady=10,
                        relief=tk.RIDGE, bd=1)
        ctrl.pack(side=tk.LEFT, fill=tk.Y, padx=(8, 4), pady=8)

        tk.Label(ctrl, text="Inequality / Equation Visualizer",
                 font=("Helvetica", 13, "bold"), bg="#f0f0f0").grid(
                     row=0, column=0, columnspan=3, pady=(0, 10))

        # --- Expression ---
        section = self._section(ctrl, "Expression  f(x, y)", row=1)
        tk.Label(section, text="f(x, y) =", bg="#f0f0f0",
                 font=("Helvetica", 10)).grid(row=0, column=0, sticky="e", padx=(0, 4))
        self.expr_var = tk.StringVar()
        expr_entry = tk.Entry(section, textvariable=self.expr_var, width=34,
                              font=("Courier", 10))
        expr_entry.grid(row=0, column=1, columnspan=2, sticky="ew", pady=2)

        tk.Label(section, text="Relation:", bg="#f0f0f0",
                 font=("Helvetica", 10)).grid(row=1, column=0, sticky="e", padx=(0, 4))
        self.relation_var = tk.StringVar(value=">0")
        rel_menu = ttk.Combobox(section, textvariable=self.relation_var,
                                values=[">0", ">=0", "<0", "<=0", "=0"],
                                state="readonly", width=8,
                                font=("Helvetica", 10))
        rel_menu.grid(row=1, column=1, sticky="w", pady=2)

        tk.Label(section, text="(tolerance for =0):", bg="#f0f0f0",
                 font=("Helvetica", 9)).grid(row=2, column=0, sticky="e", padx=(0, 4))
        self.tol_var = tk.StringVar(value="0.05")
        tk.Entry(section, textvariable=self.tol_var, width=8,
                 font=("Courier", 10)).grid(row=2, column=1, sticky="w", pady=2)

        # --- Domain ---
        section2 = self._section(ctrl, "Domain boundaries", row=3)
        for i, (lbl, attr, default) in enumerate([
            ("x min", "x_min_var", "-4"),
            ("x max", "x_max_var", "4"),
            ("y min", "y_min_var", "-4"),
            ("y max", "y_max_var", "4"),
        ]):
            tk.Label(section2, text=lbl + ":", bg="#f0f0f0",
                     font=("Helvetica", 10)).grid(row=i, column=0, sticky="e", padx=(0,4))
            var = tk.StringVar(value=default)
            setattr(self, attr, var)
            tk.Entry(section2, textvariable=var, width=10,
                     font=("Courier", 10)).grid(row=i, column=1, sticky="w", pady=2)

        # --- Resolution ---
        section3 = self._section(ctrl, "Plot settings", row=5)
        tk.Label(section3, text="Grid resolution:", bg="#f0f0f0",
                 font=("Helvetica", 10)).grid(row=0, column=0, sticky="e", padx=(0,4))
        self.resolution_var = tk.StringVar(value="400")
        tk.Entry(section3, textvariable=self.resolution_var, width=8,
                 font=("Courier", 10)).grid(row=0, column=1, sticky="w", pady=2)

        tk.Label(section3, text="Colormap:", bg="#f0f0f0",
                 font=("Helvetica", 10)).grid(row=1, column=0, sticky="e", padx=(0,4))
        self.cmap_var = tk.StringVar(value="Green/Red")
        ttk.Combobox(section3, textvariable=self.cmap_var,
                     values=["Green/Red", "Blue/Orange", "Purple/Coral", "Grayscale"],
                     state="readonly", width=14,
                     font=("Helvetica", 10)).grid(row=1, column=1, sticky="w", pady=2)

        tk.Label(section3, text="Show boundary:", bg="#f0f0f0",
                 font=("Helvetica", 10)).grid(row=2, column=0, sticky="e", padx=(0,4))
        self.show_boundary_var = tk.BooleanVar(value=True)
        tk.Checkbutton(section3, variable=self.show_boundary_var,
                       bg="#f0f0f0").grid(row=2, column=1, sticky="w")

        # --- Buttons ---
        btn_frame = tk.Frame(ctrl, bg="#f0f0f0")
        btn_frame.grid(row=7, column=0, columnspan=3, pady=(14, 2))

        plot_btn = tk.Button(btn_frame, text="  Plot  ", command=self._plot,
                             font=("Helvetica", 11, "bold"),
                             bg="#2563EB", fg="white",
                             activebackground="#1D4ED8", relief=tk.FLAT,
                             padx=14, pady=6, cursor="hand2")
        plot_btn.pack(side=tk.LEFT, padx=4)

        reset_btn = tk.Button(btn_frame, text="Reset", command=self._reset,
                              font=("Helvetica", 10),
                              bg="#e5e7eb", fg="#374151",
                              relief=tk.FLAT, padx=10, pady=6, cursor="hand2")
        reset_btn.pack(side=tk.LEFT, padx=4)

        # --- Help ---
        help_lbl = tk.Label(ctrl,
            text=(
                "Syntax hints:\n"
                "  Use * for multiplication: 3*x\n"
                "  Powers: x**2 or x^2\n"
                "  Functions: sin, cos, exp, sqrt\n"
                "  Constants: pi, e\n\n"
                "© Augustin Guibaud, 2022"
            ),
            bg="#f0f0f0", fg="#6b7280",
            font=("Helvetica", 9), justify=tk.LEFT,
            wraplength=220, padx=4, pady=4
        )
        help_lbl.grid(row=8, column=0, columnspan=3, sticky="w", pady=(10, 0))

        # bind Enter key
        self.bind("<Return>", lambda _: self._plot())

    def _section(self, parent, title, row):
        """Create a labeled section frame."""
        tk.Label(parent, text=title, bg="#f0f0f0",
                 font=("Helvetica", 10, "bold"), fg="#374151").grid(
                     row=row, column=0, columnspan=3, sticky="w",
                     pady=(10, 2))
        frame = tk.Frame(parent, bg="#f0f0f0")
        frame.grid(row=row+1, column=0, columnspan=3, sticky="ew", padx=4)
        return frame

    def _build_plot_panel(self):
        plot_frame = tk.Frame(self, bg="#ffffff", relief=tk.RIDGE, bd=1)
        plot_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True,
                        padx=(4, 8), pady=8)

        self.fig, self.ax = plt.subplots(figsize=(6.5, 5.5))
        self.fig.patch.set_facecolor("#ffffff")
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        toolbar = NavigationToolbar2Tk(self.canvas, plot_frame)
        toolbar.update()

        # Status bar
        self.status_var = tk.StringVar(value="Ready.")
        status_bar = tk.Label(plot_frame, textvariable=self.status_var,
                              bg="#e5e7eb", fg="#374151",
                              font=("Helvetica", 9), anchor="w", padx=8, pady=3)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    # ------------------------------------------------------------------
    # Core logic
    # ------------------------------------------------------------------

    def _get_colormaps(self):
        choice = self.cmap_var.get()
        schemes = {
            "Green/Red":    (np.array([0.86, 0.20, 0.20, 0.35]),   # infeasible RGBA
                             np.array([0.16, 0.70, 0.39, 0.35])),  # feasible RGBA
            "Blue/Orange":  (np.array([0.97, 0.55, 0.13, 0.35]),
                             np.array([0.22, 0.53, 0.87, 0.35])),
            "Purple/Coral": (np.array([0.85, 0.39, 0.31, 0.35]),
                             np.array([0.49, 0.36, 0.85, 0.35])),
            "Grayscale":    (np.array([0.75, 0.75, 0.75, 0.35]),
                             np.array([0.30, 0.30, 0.30, 0.35])),
        }
        return schemes.get(choice, schemes["Green/Red"])

    def _plot(self):
        expr = self.expr_var.get().strip()
        relation = self.relation_var.get()
        if not expr:
            messagebox.showerror("Input error", "Please enter an expression f(x, y).")
            return

        try:
            xmin = float(self.x_min_var.get())
            xmax = float(self.x_max_var.get())
            ymin = float(self.y_min_var.get())
            ymax = float(self.y_max_var.get())
            res  = int(self.resolution_var.get())
            tol  = float(self.tol_var.get())
        except ValueError as exc:
            messagebox.showerror("Input error", f"Invalid numeric input:\n{exc}")
            return

        if xmin >= xmax or ymin >= ymax:
            messagebox.showerror("Input error", "min must be strictly less than max.")
            return
        if res < 50 or res > 2000:
            messagebox.showerror("Input error", "Resolution must be between 50 and 2000.")
            return

        # Build grid
        xv = np.linspace(xmin, xmax, res)
        yv = np.linspace(ymin, ymax, res)
        X, Y = np.meshgrid(xv, yv)

        try:
            Z = safe_eval_expr(expr, X, Y)
        except Exception as exc:
            messagebox.showerror("Expression error",
                                 f"Could not evaluate expression:\n{exc}\n\n"
                                 "Check syntax. Use * for multiplication, ** for powers.")
            return

        # Build mask: True = feasible
        rel = relation
        if rel == ">0":
            mask = Z > 0
        elif rel == ">=0":
            mask = Z >= 0
        elif rel == "<0":
            mask = Z < 0
        elif rel == "<=0":
            mask = Z <= 0
        else:  # =0 (within tolerance)
            mask = np.abs(Z) <= tol

        # Color arrays
        infeasible_color, feasible_color = self._get_colormaps()

        # Build RGBA image
        img = np.where(mask[..., None],
                       feasible_color,
                       infeasible_color).astype(float)

        # Draw
        self.ax.clear()
        self.ax.imshow(
            img,
            origin="lower",
            extent=[xmin, xmax, ymin, ymax],
            aspect="auto",
            interpolation="nearest",
        )

        # Boundary contour
        if self.show_boundary_var.get():
            try:
                self.ax.contour(X, Y, Z, levels=[0],
                                colors=["#111111"], linewidths=1.6,
                                linestyles="--")
            except Exception:
                pass  # contour may fail for degenerate cases

        # Axes decoration
        pretty_rel = {"<0": "< 0", ">0": "> 0", "<=0": "≤ 0",
                      ">=0": "≥ 0", "=0": "= 0"}.get(relation, relation)
        self.ax.set_title(f"f(x, y) = {expr}    →    f(x, y) {pretty_rel}",
                          fontsize=10, pad=10)
        self.ax.set_xlabel("x", fontsize=11)
        self.ax.set_ylabel("y", fontsize=11)
        self.ax.set_xlim(xmin, xmax)
        self.ax.set_ylim(ymin, ymax)
        self.ax.grid(True, color="#cccccc", linewidth=0.5, linestyle=":")
        self.ax.axhline(0, color="#999999", linewidth=0.8)
        self.ax.axvline(0, color="#999999", linewidth=0.8)

        # Legend patches
        import matplotlib.patches as mpatches
        _, fc = self._get_colormaps()
        _, ic = self._get_colormaps()
        infeasible_color, feasible_color = self._get_colormaps()
        feas_patch   = mpatches.Patch(
            facecolor=feasible_color[:3], alpha=0.7,
            label=f"f(x,y) {pretty_rel}  (feasible)")
        infeas_patch = mpatches.Patch(
            facecolor=infeasible_color[:3], alpha=0.7,
            label="outside")
        handles = [feas_patch, infeas_patch]
        if self.show_boundary_var.get():
            from matplotlib.lines import Line2D
            bnd_line = Line2D([0], [0], color="#111111", linewidth=1.6,
                              linestyle="--", label="boundary f = 0")
            handles.append(bnd_line)
        self.ax.legend(handles=handles, fontsize=8, loc="upper right",
                       framealpha=0.85)

        self.fig.tight_layout()
        self.canvas.draw()

        # Count feasible fraction
        frac = mask.sum() / mask.size * 100
        self.status_var.set(
            f"Plotted on [{xmin}, {xmax}] × [{ymin}, {ymax}]  |  "
            f"Feasible pixels: {frac:.1f}%  |  Grid: {res}×{res}"
        )

    def _reset(self):
        self.expr_var.set("")
        self.relation_var.set(">0")
        self.x_min_var.set("-4")
        self.x_max_var.set("4")
        self.y_min_var.set("-4")
        self.y_max_var.set("4")
        self.resolution_var.set("400")
        self.tol_var.set("0.05")
        self.cmap_var.set("Green/Red")
        self.show_boundary_var.set(True)
        self.ax.clear()
        self.canvas.draw()
        self.status_var.set("Reset.")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = InequalityVisualizer()
    app.mainloop()
