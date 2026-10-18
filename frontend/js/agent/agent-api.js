/** 客服六接口复用公共请求层；该模块由后端允许匿名访问。 */
import { request } from "../common/api.js";

const publicRequest = (path, options = {}) => request(path, { ...options, authenticated: false });
export const CustomerAgentAPI = Object.freeze({
  chat: body => publicRequest("/agent/chat", { method: "POST", body }),
  events: status => publicRequest("/agent/events" + (status ? `?status=${encodeURIComponent(status)}` : "")),
  event: id => publicRequest(`/agent/events/${encodeURIComponent(id)}`),
  signup: body => publicRequest("/agent/events/signup", { method: "POST", body }),
  courses: category => publicRequest("/agent/courses" + (category ? `?category=${encodeURIComponent(category)}` : "")),
  faq: question => publicRequest("/agent/faq" + (question ? `?question=${encodeURIComponent(question)}` : "")),
});
