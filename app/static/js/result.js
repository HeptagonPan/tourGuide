const embeddedPlan = JSON.parse(document.querySelector("#plan-data").textContent || "null");
const storedPlan = sessionStorage.getItem("tourGuidePlan");
const plan = embeddedPlan || (storedPlan ? JSON.parse(storedPlan) : null);
const categoryLabels = {
  intercity: "往返大交通",
  accommodation: "住宿",
  dining: "餐饮",
  attractions: "门票",
  local_transport: "市内交通",
  reserve: "备用金",
};

function formatCents(cents) {
  return `¥${(cents / 100).toLocaleString("zh-CN", { minimumFractionDigits: 2 })}`;
}

function formatDate(value) {
  return new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric", weekday: "short" })
    .format(new Date(`${value}T00:00:00`));
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderRouteDiagram(day) {
  const container = document.querySelector("#route-summary");
  const previous = container.querySelector("#route-diagram");
  if (previous) previous.remove();

  const diagram = document.createElement("section");
  diagram.id = "route-diagram";
  diagram.className = "route-diagram";
  diagram.setAttribute("aria-label", "离线路线示意");

  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 100 100");
  svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "当日景点访问顺序示意");

  const longitudes = day.activities.map((activity) => activity.longitude);
  const latitudes = day.activities.map((activity) => activity.latitude);
  const minLongitude = Math.min(...longitudes);
  const maxLongitude = Math.max(...longitudes);
  const minLatitude = Math.min(...latitudes);
  const maxLatitude = Math.max(...latitudes);
  const longitudeSpan = maxLongitude - minLongitude;
  const latitudeSpan = maxLatitude - minLatitude;
  const padding = 8;
  const usable = 100 - padding * 2;
  const centered = padding + usable / 2;

  const points = day.activities.map((activity) => ({
    x: longitudeSpan === 0
      ? centered
      : padding + ((activity.longitude - minLongitude) / longitudeSpan) * usable,
    y: latitudeSpan === 0
      ? centered
      : padding + ((maxLatitude - activity.latitude) / latitudeSpan) * usable,
  }));

  if (points.length > 1) {
    const polyline = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
    polyline.setAttribute("class", "route-polyline");
    polyline.setAttribute("points", points.map((point) => `${point.x},${point.y}`).join(" "));
    svg.appendChild(polyline);
  }

  points.forEach((point, index) => {
    const stop = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    stop.setAttribute("class", "route-stop");
    stop.setAttribute("cx", String(point.x));
    stop.setAttribute("cy", String(point.y));
    stop.setAttribute("r", "2.4");
    svg.appendChild(stop);

    const number = document.createElementNS("http://www.w3.org/2000/svg", "text");
    number.setAttribute("class", "route-stop-number");
    number.setAttribute("x", String(point.x));
    number.setAttribute("y", String(point.y - 4.5));
    number.setAttribute("text-anchor", "middle");
    number.textContent = String(index + 1);
    svg.appendChild(number);
  });

  diagram.appendChild(svg);

  const detail = document.createElement("div");
  detail.className = "route-detail";
  const routeText = day.routes
    .map((route) => {
      const distance = route.distance_meters >= 1000
        ? `${(route.distance_meters / 1000).toFixed(1)} 公里`
        : `${route.distance_meters} 米`;
      return `${route.origin_name} → ${route.destination_name}：${route.duration_minutes} 分钟 · 约 ${distance} · ${route.instructions.join("；")}`;
    })
    .join("；");
  detail.textContent = routeText || "当日无需地点间路线";
  diagram.appendChild(detail);

  const note = document.createElement("p");
  note.className = "route-diagram-note";
  note.textContent = "离线路线示意 · 时间与距离为实用级估算";
  diagram.appendChild(note);

  container.appendChild(diagram);
}

function renderDay(dayIndex) {
  const day = plan.days[dayIndex];
  document.querySelectorAll("[data-day-index]").forEach((button) => {
    button.setAttribute("aria-selected", String(Number(button.dataset.dayIndex) === dayIndex));
  });
  document.querySelector("#day-timeline").innerHTML = day.activities
    .map((activity) => `
      <article class="timeline-item">
        <p class="timeline-slot">${escapeHtml(activity.slot)}</p>
        <div>
          <h3>${escapeHtml(activity.name)}</h3>
          <p>${escapeHtml(activity.region)} · 建议停留 ${activity.duration_minutes} 分钟</p>
        </div>
        <p class="timeline-cost">${formatCents(activity.cost_cents)}</p>
      </article>`)
    .join("");
  const routes = day.routes.length
    ? day.routes.map((route) => `
        <li>
          <strong>${escapeHtml(route.origin_name)} → ${escapeHtml(route.destination_name)}</strong>
          <span>${route.duration_minutes} 分钟 · ${route.distance_meters} 米 · ${formatCents(route.cost_cents)}</span>
        </li>`).join("")
    : "<li><strong>当日首站</strong><span>无需地点间路线</span></li>";
  document.querySelector("#route-summary").innerHTML = `
    <p class="section-label">${formatDate(day.date)}</p>
    <h3>当天路线</h3>
    <ol>${routes}</ol>
  `;
  renderRouteDiagram(day);
}

function renderPlan() {
  document.querySelector("#result-title").textContent = `${plan.destination} ${plan.days.length} 日行程`;
  document.querySelector("#result-narrative").textContent = plan.narrative;
  document.querySelector("#overview-dates").textContent = `${plan.request.start_date} 至 ${plan.request.end_date}`;
  document.querySelector("#overview-travelers").textContent = `${plan.request.adults + plan.request.children} 位`;
  document.querySelector("#overview-budget").textContent = formatCents(plan.request.budget_cents);
  document.querySelector("#overview-hotel").textContent = `${plan.accommodation.rooms} 间 × ${plan.accommodation.nights} 晚`;
  document.querySelector("#data-updated-at").textContent = plan.data_updated_at;

  document.querySelector("#day-tabs").innerHTML = plan.days
    .map((day, index) => `<button type="button" role="tab" data-day-index="${index}" aria-selected="${index === 0}">${formatDate(day.date)}</button>`)
    .join("");
  document.querySelectorAll("[data-day-index]").forEach((button) => {
    button.addEventListener("click", () => renderDay(Number(button.dataset.dayIndex)));
  });

  document.querySelector("#transport-options").innerHTML = plan.transport_options
    .map((option) => `<div><strong>${escapeHtml(option.name)}</strong><span>${formatCents(option.price_min_cents)} – ${formatCents(option.price_max_cents)}</span><span>${option.legs.length} 段 · ${escapeHtml(option.mode)}</span></div>`)
    .join("");
  document.querySelector("#accommodation-detail").innerHTML = `
    <p class="detail-lead">${plan.accommodation.rooms} 间客房，连续 ${plan.accommodation.nights} 晚</p>
    <p>${escapeHtml(plan.accommodation.tier)}档参考：每晚 ${formatCents(plan.accommodation.nightly_min_cents)} – ${formatCents(plan.accommodation.nightly_max_cents)}</p>`;
  const budgetRows = Object.entries(plan.budget.categories)
    .map(([category, cents]) => `<tr><th>${categoryLabels[category] || escapeHtml(category)}</th><td>${formatCents(cents)}</td></tr>`)
    .join("");
  document.querySelector("#budget-detail").innerHTML = `
    <table><tbody>${budgetRows}<tr class="budget-total"><th>预计总支出</th><td>${formatCents(plan.budget.total_cents)}</td></tr><tr><th>预算余额</th><td>${formatCents(plan.budget.remaining_cents)}</td></tr></tbody></table>`;
  document.querySelector("#source-list").innerHTML = plan.source_ids
    .map((sourceId) => `<code>${escapeHtml(sourceId)}</code>`)
    .join("");
  document.querySelector("#export-plan").disabled = false;
  renderDay(0);
}

async function exportPlan() {
  const button = document.querySelector("#export-plan");
  const message = document.querySelector("#result-message");
  button.disabled = true;
  message.textContent = "";
  try {
    const response = await fetch("/api/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(plan),
    });
    if (!response.ok) throw new Error();
    const blob = await response.blob();
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `tourGuide-上海-${plan.request.start_date.replaceAll("-", "")}.html`;
    link.click();
    URL.revokeObjectURL(link.href);
    message.textContent = "行程 HTML 已生成";
  } catch {
    message.textContent = "导出失败，请稍后重试";
  } finally {
    button.disabled = false;
  }
}

document.querySelector("#export-plan").addEventListener("click", exportPlan);
if (plan) renderPlan();
