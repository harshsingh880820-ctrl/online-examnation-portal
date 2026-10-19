(() => {
  const timer = document.getElementById("timer");
  const form = document.getElementById("submitForm");
  if (!timer || !form) return;
  const deadline = new Date(timer.dataset.deadline).getTime();
  const status = document.getElementById("saveStatus");
  let submitting = false;
  let pending = Promise.resolve();

  async function saveAnswer(input) {
    const data = new URLSearchParams();
    data.set("question_id", input.dataset.question);
    data.set("selected_option", input.value);
    status.textContent = "Saving answer…";
    try {
      const response = await fetch(`${location.pathname.replace(/\/start$/, "")}/save-answer`, {
        method: "POST",
        headers: {"Content-Type": "application/x-www-form-urlencoded"},
        body: data.toString(),
        credentials: "same-origin"
      });
      if (!response.ok) throw new Error("Could not save answer");
      status.textContent = "All changes saved.";
    } catch (error) {
      status.textContent = "Save failed. Check your connection and select the answer again.";
    }
  }

  document.querySelectorAll('input[type="radio"][data-question]').forEach(input => {
    input.addEventListener("change", () => {
      pending = pending.then(() => saveAnswer(input));
    });
  });

  function submitNow() {
    if (submitting) return;
    submitting = true;
    document.getElementById("submitBtn").disabled = true;
    status.textContent = "Submitting exam…";
    pending.finally(() => form.submit());
  }

  function updateTimer() {
    const remaining = Math.max(0, Math.floor((deadline - Date.now()) / 1000));
    const minutes = Math.floor(remaining / 60);
    const seconds = remaining % 60;
    timer.textContent = `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
    timer.classList.toggle("timer-danger", remaining <= 60);
    if (remaining <= 0) submitNow();
  }
  form.addEventListener("submit", event => {
    if (submitting) return;
    event.preventDefault();
    if (confirm("Submit your examination now? You cannot change answers after submission.")) submitNow();
  });
  updateTimer();
  setInterval(updateTimer, 1000);
})();