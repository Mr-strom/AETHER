import type { RuntimeProfile, RuntimeState } from "./types";

type LocalLlamaContext = {
  completion: (params: Record<string, unknown>, callback?: (data: { token?: string }) => void) => Promise<{ text: string; timings?: Record<string, unknown> }>;
  stopCompletion: () => Promise<void>;
  release: () => Promise<void>;
};

let context: LocalLlamaContext | null = null;
let activeModelPath: string | undefined;

function profileSettings(profile: RuntimeProfile) {
  return profile === "standard"
    ? { n_ctx: 3072, n_threads: 4, n_predict: 192 }
    : { n_ctx: 2048, n_threads: 3, n_predict: 128 };
}

export async function loadOnDeviceModel(modelPath: string, profile: RuntimeProfile): Promise<RuntimeState> {
  await releaseOnDeviceModel();
  try {
    const llama = require("llama.rn") as { initLlama: (options: Record<string, unknown>) => Promise<LocalLlamaContext> };
    const settings = profileSettings(profile);
    context = await llama.initLlama({
      model: modelPath,
      n_ctx: settings.n_ctx,
      n_threads: settings.n_threads,
      n_gpu_layers: 0,
      use_mlock: false,
    });
    activeModelPath = modelPath;
    return {
      profile,
      modelPath,
      modelName: modelPath.split("/").pop(),
      loaded: true,
      loading: false,
      mode: "local_model",
      note: "Local GGUF model loaded. Generation stays on this device.",
    };
  } catch (error) {
    context = null;
    activeModelPath = undefined;
    return {
      profile,
      modelPath,
      loaded: false,
      loading: false,
      mode: "extractive",
      note: `Local model could not load: ${error instanceof Error ? error.message : "unknown native runtime error"}`,
    };
  }
}

export async function generateOnDevice(
  prompt: string,
  profile: RuntimeProfile,
  onToken: (token: string) => void,
): Promise<string> {
  if (!context) throw new Error("No local GGUF model is loaded.");
  const settings = profileSettings(profile);
  const result = await context.completion(
    {
      prompt,
      n_predict: settings.n_predict,
      temperature: 0.1,
      top_k: 20,
      top_p: 0.9,
      stop: ["</s>", "<|im_end|>", "<|endoftext|>"],
    },
    (data) => {
      if (data.token) onToken(data.token);
    },
  );
  return result.text.trim();
}

export async function stopOnDeviceGeneration(): Promise<void> {
  if (context) await context.stopCompletion();
}

export async function releaseOnDeviceModel(): Promise<void> {
  if (context) await context.release();
  context = null;
  activeModelPath = undefined;
}

export function getLoadedModelPath(): string | undefined {
  return activeModelPath;
}
