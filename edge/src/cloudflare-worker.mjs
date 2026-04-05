import { handleLiteRequest } from "./lite.mjs";

export default {
  async fetch(request, env) {
    return handleLiteRequest(request, env);
  },
};
