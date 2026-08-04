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
    <p class="source-note">路线来源：高德 Web 服务</p>`;
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
