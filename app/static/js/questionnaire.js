const form = document.querySelector("#questionnaire");
const steps = [...document.querySelectorAll(".question-step")];
const previousButton = document.querySelector("#previous-step");
const nextButton = document.querySelector("#next-step");
const errorRegion = document.querySelector("#form-error");
const progress = document.querySelector("#question-progress");
const progressBar = progress.querySelector("span");
const stepNumber = document.querySelector("#step-number");
const interestOptions = document.querySelector("#interest-options");

let currentStep = 1;
let optionData = { cities: [], interests: [] };

const tripDraft = {
  origin_city: "",
  adults: 2,
  children: 0,
  rooms: null,
  relationship: "couple",
  start_date: "",
  end_date: "",
  budget_cents: 600000,
  budget_includes_intercity: true,
  interests: [],
  intercity_preference: "balanced",
  local_transport_preference: "balanced",
};

const labels = {
  balanced: "综合平衡",
  rail: "优先高铁",
  flight: "优先航班",
  cheapest: "优先低价",
  fastest: "优先省时",
  metro: "优先地铁",
  less_walking: "减少步行",
  taxi: "适当打车",
};

function syncDraft() {
  const data = new FormData(form);
  tripDraft.origin_city = String(data.get("origin_city") || "");
  tripDraft.adults = Number(data.get("adults") || 0);
  tripDraft.children = Number(data.get("children") || 0);
  tripDraft.rooms = data.get("rooms") ? Number(data.get("rooms")) : null;
  tripDraft.relationship = String(data.get("relationship") || "couple");
  tripDraft.start_date = String(data.get("start_date") || "");
  tripDraft.end_date = String(data.get("end_date") || "");
  tripDraft.budget_cents = Math.round(Number(data.get("budget_yuan") || 0) * 100);
  tripDraft.budget_includes_intercity = data.has("budget_includes_intercity");
  tripDraft.interests = data.getAll("interests").map(String);
  tripDraft.intercity_preference = String(data.get("intercity_preference") || "balanced");
  tripDraft.local_transport_preference = String(data.get("local_transport_preference") || "balanced");
  updateSummary();
}

function updateSummary() {
  const interestLabels = optionData.interests
    .filter((interest) => tripDraft.interests.includes(interest.id))
    .map((interest) => interest.label);
  const dateText = tripDraft.start_date && tripDraft.end_date
    ? `${tripDraft.start_date} 至 ${tripDraft.end_date}`
    : "待选择";
  const summary = {
    origin_city: tripDraft.origin_city || "待选择",
    travelers: tripDraft.rooms
      ? `${tripDraft.adults + tripDraft.children} 位 / ${tripDraft.rooms} 间房`
      : `${tripDraft.adults + tripDraft.children} 位 / 房间自动计算`,
    dates: dateText,
    budget: `¥${(tripDraft.budget_cents / 100).toLocaleString("zh-CN")}`,
    interests: interestLabels.join("、") || "待选择",
    transport: labels[tripDraft.intercity_preference] || "综合平衡",
  };
  Object.entries(summary).forEach(([key, value]) => {
    const target = document.querySelector(`[data-summary="${key}"]`);
    if (target) target.textContent = value;
  });
}

function validateStep(step) {
  syncDraft();
  if (step === 1 && !tripDraft.origin_city) return "请选择出发城市";
  if (step === 2) {
    if (tripDraft.adults < 1) return "成人至少为 1 位";
    if (tripDraft.children < 0) return "儿童人数不能为负数";
    if (tripDraft.rooms && tripDraft.rooms > tripDraft.adults + tripDraft.children) {
      return "房间数不能超过同行总人数";
    }
  }
  if (step === 3) {
    if (!tripDraft.start_date || !tripDraft.end_date) return "请选择完整日期";
    const start = new Date(`${tripDraft.start_date}T00:00:00`);
    const end = new Date(`${tripDraft.end_date}T00:00:00`);
    const days = Math.round((end - start) / 86400000) + 1;
    if (days < 1) return "结束日期不能早于出发日期";
    if (days > 14) return "旅行时间最多为 14 天";
  }
  if (step === 4 && tripDraft.budget_cents < 10000) return "预算至少为 ¥100";
  if (step === 5 && tripDraft.interests.length === 0) return "至少选择一项旅行兴趣";
  return "";
}

function renderStep() {
  steps.forEach((step) => { step.hidden = Number(step.dataset.step) !== currentStep; });
  progress.setAttribute("aria-valuenow", String(currentStep));
  progressBar.style.width = `${(currentStep / steps.length) * 100}%`;
  stepNumber.textContent = String(currentStep).padStart(2, "0");
  previousButton.disabled = currentStep === 1;
  nextButton.textContent = currentStep === steps.length ? "生成行程" : "下一步";
  errorRegion.textContent = "";
  if (currentStep === 7) renderConfirmation();
  steps[currentStep - 1].querySelector("legend")?.focus?.();
}

function renderConfirmation() {
  syncDraft();
  const selectedInterests = optionData.interests
    .filter((item) => tripDraft.interests.includes(item.id))
    .map((item) => item.label)
    .join("、");
  const rows = [
    ["出发城市", tripDraft.origin_city],
    ["同行人数", `${tripDraft.adults} 位成人，${tripDraft.children} 位儿童`],
    ["房间", tripDraft.rooms ? `${tripDraft.rooms} 间` : "按同行关系自动计算"],
    ["日期", `${tripDraft.start_date} 至 ${tripDraft.end_date}`],
    ["预算", `¥${(tripDraft.budget_cents / 100).toLocaleString("zh-CN")}`],
    ["旅行兴趣", selectedInterests],
  ];
  document.querySelector("#confirmation-list").innerHTML = rows
    .map(([term, description]) => `<div><dt>${term}</dt><dd>${description}</dd></div>`)
    .join("");
}

async function submitPlan() {
  nextButton.disabled = true;
  previousButton.disabled = true;
  nextButton.textContent = "正在规划";
  errorRegion.textContent = "";
  try {
    const response = await fetch("/api/plans", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(tripDraft),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || "暂时无法生成行程");
    sessionStorage.setItem("tourGuidePlan", JSON.stringify(body));
    window.location.assign("/result");
  } catch (error) {
    errorRegion.textContent = error.message || "暂时无法生成行程，请稍后重试";
    nextButton.disabled = false;
    previousButton.disabled = false;
    nextButton.textContent = "生成行程";
  }
}

nextButton.addEventListener("click", async () => {
  const error = validateStep(currentStep);
  if (error) { errorRegion.textContent = error; return; }
  if (currentStep === steps.length) { await submitPlan(); return; }
  currentStep += 1;
  renderStep();
});

previousButton.addEventListener("click", () => {
  if (currentStep > 1) currentStep -= 1;
  renderStep();
});

form.addEventListener("input", syncDraft);
form.addEventListener("change", syncDraft);

async function loadOptions() {
  try {
    const response = await fetch("/api/options");
    if (!response.ok) throw new Error();
    optionData = await response.json();
    const citySelect = document.querySelector("#origin-city");
    citySelect.innerHTML = '<option value="">请选择</option>' + optionData.cities
      .map((city) => `<option value="${city.name}">${city.name}</option>`)
      .join("");
    interestOptions.innerHTML = optionData.interests
      .map((interest) => `<label class="choice-tile"><input type="checkbox" name="interests" value="${interest.id}"><span>${interest.label}</span></label>`)
      .join("");
  } catch {
    errorRegion.textContent = "选项加载失败，请刷新页面重试";
    nextButton.disabled = true;
  }
}

loadOptions().then(() => { syncDraft(); renderStep(); });
