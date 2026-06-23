import tkinter as tk
import threading
import time
from datetime import datetime
from modules.data_connector import get_latest_quote

# ── Color palette ─────────────────────────────────────────────────────────────
BG        = "#050a0f"
BG2       = "#0a1018"
BG3       = "#0f1923"
PANEL     = "#111c27"
BORDER    = "#1a2d42"
ACCENT    = "#00d4ff"
GREEN     = "#00ff88"
RED       = "#ff3355"
YELLOW    = "#ffd700"
WHITE     = "#e8f4f8"
MUTED     = "#4a6fa5"
DIM       = "#1e3a5f"
FONT_MONO = "Courier New"

class MarketTerminal:
    def __init__(self, root):
        self.root = root
        self.root.title("APEX TERMINAL  v1.0")
        self.root.configure(bg=BG)
        self.root.geometry("960x680")
        self.root.resizable(True, True)
        self.running = False
        self.quote_history = []
        self.flash_job = None

        self._build_ui()
        self._start_clock()
        self._animate_scanline()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_topbar()
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        body.columnconfigure(0, weight=2)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        left = tk.Frame(body, bg=BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)
        self._build_quote_panel(left)
        self._build_chart_panel(left)

        right = tk.Frame(body, bg=BG)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)
        self._build_controls(right)
        self._build_stats(right)
        self._build_log(right)

    def _build_topbar(self):
        bar = tk.Frame(self.root, bg=BG2, height=44)
        bar.pack(fill=tk.X, padx=10, pady=(8, 6))
        bar.pack_propagate(False)

        tk.Label(bar, text="▣ APEX", font=(FONT_MONO, 15, "bold"),
                 bg=BG2, fg=ACCENT).pack(side=tk.LEFT, padx=14, pady=6)
        tk.Label(bar, text="MARKET TERMINAL", font=(FONT_MONO, 9),
                 bg=BG2, fg=MUTED).pack(side=tk.LEFT, pady=6)

        self.clock_var = tk.StringVar(value="")
        tk.Label(bar, textvariable=self.clock_var, font=(FONT_MONO, 10),
                 bg=BG2, fg=YELLOW).pack(side=tk.RIGHT, padx=14)

        self.status_dot = tk.Label(bar, text="●", font=(FONT_MONO, 12),
                                   bg=BG2, fg=MUTED)
        self.status_dot.pack(side=tk.RIGHT, padx=2)
        self.status_label = tk.Label(bar, text="OFFLINE", font=(FONT_MONO, 9),
                                     bg=BG2, fg=MUTED)
        self.status_label.pack(side=tk.RIGHT)

        tk.Frame(self.root, bg=ACCENT, height=1).pack(fill=tk.X, padx=10)

    def _build_quote_panel(self, parent):
        panel = tk.Frame(parent, bg=PANEL, relief="flat")
        panel.grid(row=0, column=0, sticky="ew", pady=(0, 6))

        hdr = tk.Frame(panel, bg=BG3)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="  LIVE QUOTE", font=(FONT_MONO, 8, "bold"),
                 bg=BG3, fg=MUTED).pack(side=tk.LEFT, pady=4)
        self.symbol_label = tk.Label(hdr, text="", font=(FONT_MONO, 10, "bold"),
                                     bg=BG3, fg=ACCENT)
        self.symbol_label.pack(side=tk.RIGHT, padx=10, pady=4)

        price_frame = tk.Frame(panel, bg=PANEL)
        price_frame.pack(fill=tk.X, padx=14, pady=10)

        self.price_var = tk.StringVar(value="─ ─ ─ . ─ ─")
        self.price_label = tk.Label(price_frame, textvariable=self.price_var,
                                    font=(FONT_MONO, 38, "bold"),
                                    bg=PANEL, fg=WHITE)
        self.price_label.pack(side=tk.LEFT)

        # ✅ Fixed: store Label reference, not StringVar
        self.change_label = tk.Label(price_frame, text="",
                                     font=(FONT_MONO, 13), bg=PANEL, fg=GREEN)
        self.change_label.pack(side=tk.LEFT, padx=14, pady=14)

        tk.Frame(panel, bg=BORDER, height=1).pack(fill=tk.X, padx=10)
        row = tk.Frame(panel, bg=PANEL)
        row.pack(fill=tk.X, padx=10, pady=8)

        self.bid_var = tk.StringVar(value="---")
        self.ask_var = tk.StringVar(value="---")
        self.spd_var = tk.StringVar(value="---")

        for label, var, color, col in [
            ("BID",    self.bid_var, GREEN,  0),
            ("ASK",    self.ask_var, RED,    1),
            ("SPREAD", self.spd_var, YELLOW, 2),
        ]:
            f = tk.Frame(row, bg=PANEL)
            f.grid(row=0, column=col, padx=20, sticky="w")
            tk.Label(f, text=label, font=(FONT_MONO, 8),
                     bg=PANEL, fg=MUTED).pack(anchor="w")
            tk.Label(f, textvariable=var, font=(FONT_MONO, 18, "bold"),
                     bg=PANEL, fg=color).pack(anchor="w")

        self.mini_canvas = tk.Canvas(panel, bg=BG3, height=4,
                                     highlightthickness=0)
        self.mini_canvas.pack(fill=tk.X)

    def _build_chart_panel(self, parent):
        frame = tk.Frame(parent, bg=PANEL)
        frame.grid(row=1, column=0, sticky="nsew", pady=(0, 0))
        frame.rowconfigure(1, weight=1)
        frame.columnconfigure(0, weight=1)

        hdr = tk.Frame(frame, bg=BG3)
        hdr.grid(row=0, column=0, sticky="ew")
        tk.Label(hdr, text="  PRICE HISTORY  (tick feed)",
                 font=(FONT_MONO, 8, "bold"), bg=BG3, fg=MUTED).pack(
                 side=tk.LEFT, pady=4)

        self.spark_canvas = tk.Canvas(frame, bg=BG3, highlightthickness=0,
                                      height=120)
        self.spark_canvas.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)

    def _build_controls(self, parent):
        frame = tk.Frame(parent, bg=PANEL)
        frame.grid(row=0, column=0, sticky="ew", pady=(0, 6))

        hdr = tk.Frame(frame, bg=BG3)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="  SYMBOL SELECT", font=(FONT_MONO, 8, "bold"),
                 bg=BG3, fg=MUTED).pack(side=tk.LEFT, pady=4)

        inner = tk.Frame(frame, bg=PANEL)
        inner.pack(fill=tk.X, padx=10, pady=10)

        self.ticker_entry = tk.Entry(inner, font=(FONT_MONO, 16, "bold"),
                                     width=8, bg=BG2, fg=ACCENT,
                                     insertbackground=ACCENT,
                                     relief="flat", bd=4,
                                     justify="center")
        self.ticker_entry.insert(0, "AAPL")
        self.ticker_entry.pack(fill=tk.X, pady=(0, 8))
        self.ticker_entry.bind("<Return>", lambda e: self.start_stream())

        btn_row = tk.Frame(inner, bg=PANEL)
        btn_row.pack(fill=tk.X)

        self.start_btn = tk.Button(btn_row, text="▶  CONNECT",
                                   font=(FONT_MONO, 10, "bold"),
                                   bg=GREEN, fg=BG, activebackground="#00cc77",
                                   relief="flat", bd=0, pady=6,
                                   command=self.start_stream, cursor="hand2")
        self.start_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        self.stop_btn = tk.Button(btn_row, text="■  STOP",
                                  font=(FONT_MONO, 10, "bold"),
                                  bg=DIM, fg=MUTED, activebackground=RED,
                                  relief="flat", bd=0, pady=6,
                                  command=self.stop_stream, cursor="hand2")
        self.stop_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Frame(frame, bg=BORDER, height=1).pack(fill=tk.X, padx=10)
        quick = tk.Frame(frame, bg=PANEL)
        quick.pack(fill=tk.X, padx=10, pady=8)
        tk.Label(quick, text="QUICK:", font=(FONT_MONO, 8),
                 bg=PANEL, fg=MUTED).pack(side=tk.LEFT)
        for sym in ["AAPL", "TSLA", "NVDA", "SPY", "MSFT"]:
            tk.Button(quick, text=sym, font=(FONT_MONO, 8),
                      bg=DIM, fg=ACCENT, activebackground=BG3,
                      relief="flat", bd=0, padx=6, pady=2,
                      cursor="hand2",
                      command=lambda s=sym: self._quick_select(s)).pack(
                      side=tk.LEFT, padx=2)

    def _build_stats(self, parent):
        frame = tk.Frame(parent, bg=PANEL)
        frame.grid(row=1, column=0, sticky="nsew", pady=(0, 6))
        frame.rowconfigure(1, weight=1)
        frame.columnconfigure(0, weight=1)

        hdr = tk.Frame(frame, bg=BG3)
        hdr.grid(row=0, column=0, sticky="ew")
        tk.Label(hdr, text="  STATS", font=(FONT_MONO, 8, "bold"),
                 bg=BG3, fg=MUTED).pack(side=tk.LEFT, pady=4)

        stats = tk.Frame(frame, bg=PANEL)
        stats.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        stats.columnconfigure(1, weight=1)

        self.hi_var   = tk.StringVar(value="---")
        self.lo_var   = tk.StringVar(value="---")
        self.tick_var = tk.StringVar(value="---")
        self.avg_var  = tk.StringVar(value="---")
        self.lat_var  = tk.StringVar(value="---")

        rows = [
            ("SESSION HIGH", self.hi_var),
            ("SESSION LOW",  self.lo_var),
            ("TICK COUNT",   self.tick_var),
            ("AVG MID",      self.avg_var),
            ("LATENCY",      self.lat_var),
        ]
        for i, (label, var) in enumerate(rows):
            tk.Label(stats, text=label, font=(FONT_MONO, 8),
                     bg=PANEL, fg=MUTED, anchor="w").grid(
                     row=i*2, column=0, sticky="w", pady=(6, 0))
            tk.Label(stats, textvariable=var, font=(FONT_MONO, 12, "bold"),
                     bg=PANEL, fg=WHITE, anchor="e").grid(
                     row=i*2, column=1, sticky="e", pady=(6, 0), padx=(8, 0))
            tk.Frame(stats, bg=BORDER, height=1).grid(
                     row=i*2+1, column=0, columnspan=2, sticky="ew", pady=(4, 0))

    def _build_log(self, parent):
        frame = tk.Frame(parent, bg=PANEL)
        frame.grid(row=2, column=0, sticky="nsew")
        frame.rowconfigure(1, weight=1)
        frame.columnconfigure(0, weight=1)

        hdr = tk.Frame(frame, bg=BG3)
        hdr.grid(row=0, column=0, sticky="ew")
        tk.Label(hdr, text="  FEED LOG", font=(FONT_MONO, 8, "bold"),
                 bg=BG3, fg=MUTED).pack(side=tk.LEFT, pady=4)

        self.log_text = tk.Text(frame, font=(FONT_MONO, 8),
                                bg=BG2, fg=MUTED,
                                relief="flat", bd=0,
                                state=tk.DISABLED, height=7,
                                wrap=tk.WORD)
        self.log_text.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)
        self.log_text.tag_config("green", foreground=GREEN)
        self.log_text.tag_config("red",   foreground=RED)
        self.log_text.tag_config("cyan",  foreground=ACCENT)
        self.log_text.tag_config("dim",   foreground=MUTED)

    # ── Logic ─────────────────────────────────────────────────────────────────

    def start_stream(self):
        if self.running:
            return
        sym = self.ticker_entry.get().upper().strip()
        if not sym:
            return
        self.running = True
        self.quote_history.clear()
        self.symbol_label.config(text=sym)
        self.status_dot.config(fg=GREEN)
        self.status_label.config(text="LIVE ", fg=GREEN)
        self.start_btn.config(bg=DIM, fg=MUTED)
        self.stop_btn.config(bg=RED, fg=WHITE)
        self._log(f"[{self._ts()}] CONNECTED  {sym}", "cyan")
        t = threading.Thread(target=self._fetch_loop, args=(sym,), daemon=True)
        t.start()

    def stop_stream(self):
        self.running = False
        self.status_dot.config(fg=MUTED)
        self.status_label.config(text="OFFLINE", fg=MUTED)
        self.start_btn.config(bg=GREEN, fg=BG)
        self.stop_btn.config(bg=DIM, fg=MUTED)
        self._log(f"[{self._ts()}] DISCONNECTED", "red")

    def _fetch_loop(self, symbol):
        prev_bid = None
        tick_count = 0
        while self.running:
            t0 = time.time()
            try:
                quote = get_latest_quote(symbol)
                latency = int((time.time() - t0) * 1000)
                bid = float(quote.bid_price)
                ask = float(quote.ask_price)
                spread = round(ask - bid, 4) if ask > 0 else 0.0
                mid = round((bid + ask) / 2, 2) if ask > 0 else bid
                tick_count += 1

                self.quote_history.append(mid)
                if len(self.quote_history) > 120:
                    self.quote_history.pop(0)

                hi  = max(self.quote_history)
                lo  = min(self.quote_history)
                avg = round(sum(self.quote_history) / len(self.quote_history), 2)

                chg = ""
                chg_color = WHITE
                if prev_bid is not None:
                    delta = round(bid - prev_bid, 2)
                    if delta > 0:
                        chg = f"▲ +{delta:.2f}"
                        chg_color = GREEN
                    elif delta < 0:
                        chg = f"▼ {delta:.2f}"
                        chg_color = RED

                prev_bid = bid

                self.root.after(0, self._update_ui,
                                bid, ask, spread, mid, chg, chg_color,
                                hi, lo, tick_count, avg, latency, symbol)
            except Exception as e:
                self.root.after(0, self._log,
                                f"[{self._ts()}] ERR: {e}", "red")

            time.sleep(3)

    def _update_ui(self, bid, ask, spread, mid, chg, chg_color,
                   hi, lo, ticks, avg, latency, symbol):
        # Price + change
        self.price_var.set(f"{mid:,.2f}")
        self.price_label.config(fg=chg_color if chg else WHITE)
        # ✅ Fixed: use .config() on the Label, not StringVar
        self.change_label.config(text=chg, fg=chg_color)

        # Bid / Ask / Spread
        self.bid_var.set(f"{bid:,.2f}")
        self.ask_var.set(f"{ask:,.2f}")
        self.spd_var.set(f"{spread:.4f}")

        # Stats
        self.hi_var.set(f"{hi:,.2f}")
        self.lo_var.set(f"{lo:,.2f}")
        self.tick_var.set(str(ticks))
        self.avg_var.set(f"{avg:,.2f}")
        self.lat_var.set(f"{latency} ms")

        # Sparkline + flash + log
        self._draw_spark()
        self._flash_price(chg_color)
        tag = "green" if "▲" in chg else ("red" if "▼" in chg else "dim")
        self._log(
            f"[{self._ts()}]  {symbol}  bid={bid:.2f}  ask={ask:.2f}  "
            f"spd={spread:.4f}  lat={latency}ms", tag)

    def _draw_spark(self):
        c = self.spark_canvas
        c.delete("all")
        w = c.winfo_width() or 400
        h = c.winfo_height() or 120
        data = self.quote_history
        if len(data) < 2:
            return

        lo, hi = min(data), max(data)
        rng = hi - lo or 1

        def xy(i, v):
            x = int(i / (len(data) - 1) * w)
            y = int(h - (v - lo) / rng * (h - 16) - 8)
            return x, y

        for i in range(4):
            y = int(h * i / 3)
            c.create_line(0, y, w, y, fill=BORDER, dash=(2, 6))

        pts = []
        for i, v in enumerate(data):
            pts.extend(xy(i, v))

        last_x, last_y = xy(len(data)-1, data[-1])
        fill_pts = [0, h] + pts + [last_x, h]
        c.create_polygon(fill_pts, fill=DIM, outline="")
        c.create_line(pts, fill=ACCENT, width=1.5, smooth=True)
        c.create_oval(last_x-4, last_y-4, last_x+4, last_y+4,
                      fill=ACCENT, outline=WHITE, width=1)

        c.create_text(4, 8,    text=f"H {hi:.2f}",
                      font=(FONT_MONO, 7), fill=GREEN, anchor="w")
        c.create_text(4, h-6,  text=f"L {lo:.2f}",
                      font=(FONT_MONO, 7), fill=RED,   anchor="w")

    def _flash_price(self, color):
        if self.flash_job:
            self.root.after_cancel(self.flash_job)
        self.price_label.config(bg=color if color != WHITE else PANEL)
        self.flash_job = self.root.after(
            200, lambda: self.price_label.config(bg=PANEL))

    def _quick_select(self, sym):
        self.ticker_entry.delete(0, tk.END)
        self.ticker_entry.insert(0, sym)
        if self.running:
            self.stop_stream()
            self.root.after(300, self.start_stream)
        else:
            self.start_stream()

    def _log(self, msg, tag="dim"):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, msg + "\n", tag)
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _start_clock(self):
        now = datetime.now().strftime("  %Y-%m-%d  %H:%M:%S")
        self.clock_var.set(now)
        self.root.after(1000, self._start_clock)

    def _animate_scanline(self):
        self.mini_canvas.delete("all")
        w = self.mini_canvas.winfo_width() or 600
        x = int(time.time() * 80) % (w + 40) - 20
        self.mini_canvas.create_rectangle(x, 0, x+40, 4,
                                          fill=ACCENT, outline="")
        self.root.after(40, self._animate_scanline)

    @staticmethod
    def _ts():
        return datetime.now().strftime("%H:%M:%S")


def launch_ui():
    root = tk.Tk()
    app = MarketTerminal(root)
    root.mainloop()