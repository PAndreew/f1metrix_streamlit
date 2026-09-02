type DriverYear = { year: number; score: number; low: number; high: number };

declare const Chart: new (element: HTMLCanvasElement, config: object) => object;

async function renderCareerChart(canvas: HTMLCanvasElement): Promise<void> {
  const driver = canvas.dataset.driver;
  const response = await fetch(`/api/drivers/${encodeURIComponent(driver ?? "")}/years`);
  if (!response.ok) return;
  const rows = (await response.json()) as DriverYear[];
  new Chart(canvas, {
    type: "line",
    data: {
      labels: rows.map((row) => row.year),
      datasets: [
        {
          label: "Lower bound",
          data: rows.map((row) => row.low),
          borderColor: "transparent",
          pointRadius: 0,
        },
        {
          label: "94% interval",
          data: rows.map((row) => row.high),
          borderColor: "transparent",
          backgroundColor: "rgba(32,88,212,.12)",
          fill: "-1",
          pointRadius: 0,
        },
        {
          label: "Skill estimate",
          data: rows.map((row) => row.score),
          borderColor: "#e10600",
          backgroundColor: "#e10600",
          borderWidth: 2,
          pointRadius: 3,
          tension: 0.15,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { intersect: false, mode: "index" },
      scales: { x: { grid: { display: false } }, y: { title: { display: true, text: "Adjusted skill" } } },
      plugins: { legend: { align: "start" } },
    },
  });
}

document.querySelectorAll<HTMLCanvasElement>(".career-chart").forEach((canvas) => {
  void renderCareerChart(canvas);
});
