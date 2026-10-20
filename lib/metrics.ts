export function track(event: "FILTRO" | "CLICK_FICHA" | "QR_MOSTRADO", businessId?: string) {
  void fetch("/api/quibar/metrics", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ event, business_id: businessId }) }).catch(() => {});
}
