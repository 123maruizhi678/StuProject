import { ApiError, readSession, request } from "../common/api.js";

export async function requestReport(method, path, body, headers) {
  const token = readSession()?.accessToken;
  const data = await request(path, { method, body, headers });
  if (!token || readSession()?.accessToken !== token) throw new ApiError("登录会话已变化，请重新进入报告模块。", 401);
  return data;
}

export function createReportGenerator(send = requestReport) {
  const pending = new Map();
  return {
    async generate(body) {
      const signature = JSON.stringify(body);
      if (!pending.has(signature)) pending.set(signature, `report-${crypto.randomUUID()}`);
      const result = await send("POST", "/report/generate", body, { "Idempotency-Key": pending.get(signature) });
      pending.delete(signature);
      return result;
    },
    reset: () => pending.clear(),
  };
}

export function toBeijingIso(value) {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?$/.test(value)) throw new Error("请填写有效的北京时间。");
  const iso = `${value.length === 16 ? `${value}:00` : value}+08:00`;
  if (!Number.isFinite(Date.parse(iso))) throw new Error("请填写有效的北京时间。");
  return iso;
}
