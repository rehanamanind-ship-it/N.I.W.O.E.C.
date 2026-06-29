#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use eframe::egui;
use rfd::FileDialog;
use sysinfo::{System, SystemExt};
use std::path::PathBuf;

// ------------------------------------------------------------
// 1. Host hardware detection
// ------------------------------------------------------------
#[derive(Debug, Clone)]
struct HostSpecs {
    cpu_cores: u32,
    cpu_freq_mhz: u32,
    ram_mb: u64,
    gpu_vram_mb: u32,
}

fn detect_host() -> HostSpecs {
    let mut sys = System::new_all();
    sys.refresh_all();
    let cpu_cores = sys.cpus().len() as u32;
    let cpu_freq = sys
        .cpus()
        .first()
        .map(|c| c.frequency())
        .unwrap_or(0) as u32;
    let ram_mb = sys.total_memory() / 1_048_576;
    HostSpecs {
        cpu_cores,
        cpu_freq_mhz: cpu_freq,
        ram_mb,
        gpu_vram_mb: 4096, // manually adjustable by the user
    }
}

// ------------------------------------------------------------
// 2. AI model wrapper (ONNX + tokenizer)
// ------------------------------------------------------------
struct AiModel {
    session: ort::Session,
    tokenizer: tokenizers::Tokenizer,
    max_len: usize,
}

impl AiModel {
    fn new() -> Self {
        let model_path = find_file("models/model.onnx");
        let tokenizer_path = find_file("models/tokenizer.json");

        let session = ort::Session::builder()
            .unwrap()
            .with_model_from_file(model_path)
            .unwrap();

        let tokenizer = tokenizers::Tokenizer::from_file(tokenizer_path).unwrap();

        Self {
            session,
            tokenizer,
            max_len: 128, // must match training
        }
    }

    fn predict(&self, requirements: &str, target: &TargetSpecs) -> (bool, String) {
        // Tokenize
        let encoding = self
            .tokenizer
            .encode(requirements, true)
            .unwrap();

        let mut input_ids = vec![0_i64; self.max_len];
        let mut attention_mask = vec![0_i64; self.max_len];
        for (i, &id) in encoding.get_ids().iter().enumerate() {
            if i >= self.max_len {
                break;
            }
            input_ids[i] = id as i64;
            attention_mask[i] = 1;
        }

        // Normalised hardware features
        let hw = vec![
            target.cpu_cores as f32 / 64.0,
            target.ram_mb as f32 / 65536.0,
            target.gpu_vram_mb as f32 / 24576.0,
        ];

        // ONNX tensors
        let input_ids_tensor = ort::Tensor::from_slice(&input_ids, &[1, self.max_len]).unwrap();
        let attention_mask_tensor = ort::Tensor::from_slice(&attention_mask, &[1, self.max_len]).unwrap();
        let hw_tensor = ort::Tensor::from_slice(&hw, &[1, 3]).unwrap();

        let outputs = self
            .session
            .run(vec![input_ids_tensor, attention_mask_tensor, hw_tensor])
            .unwrap();

        let pred: f32 = outputs[0]
            .try_extract::<f32>()
            .unwrap()
            .view()
            .to_vec()[0];

        let works = pred > 0.5;
        let confidence = if works { pred } else { 1.0 - pred };
        let explanation = if works {
            format!(
                "AI confidence: {:.0}% — App is likely to meet requirements on this hardware.",
                confidence * 100.0
            )
        } else {
            format!(
                "AI confidence: {:.0}% — App may not meet requirements. Consider optimising.",
                confidence * 100.0
            )
        };

        (works, explanation)
    }
}

/// Search for a file next to the executable, then fallback to CWD.
fn find_file(filename: &str) -> PathBuf {
    if let Ok(exe_path) = std::env::current_exe() {
        if let Some(exe_dir) = exe_path.parent() {
            let candidate = exe_dir.join(filename);
            if candidate.exists() {
                return candidate;
            }
        }
    }
    PathBuf::from(filename)
}

// ------------------------------------------------------------
// 3. Target specification (user input)
// ------------------------------------------------------------
#[derive(Debug, Clone)]
struct TargetSpecs {
    cpu_cores: u32,
    ram_mb: u64,
    gpu_vram_mb: u32,
}

// ------------------------------------------------------------
// 4. Application state
// ------------------------------------------------------------
struct NiwoecApp {
    host: HostSpecs,
    target: TargetSpecs,
    ai_model: Option<AiModel>,
    output_text: String,
    output_color: egui::Color32,
    user_gpu_vram: u32, // user‑adjustable host GPU VRAM
}

impl Default for NiwoecApp {
    fn default() -> Self {
        let host = detect_host();
        Self {
            host: host.clone(),
            target: TargetSpecs {
                cpu_cores: host.cpu_cores,
                ram_mb: host.ram_mb,
                gpu_vram_mb: host.gpu_vram_mb,
            },
            ai_model: None,
            output_text: String::new(),
            output_color: egui::Color32::WHITE,
            user_gpu_vram: host.gpu_vram_mb,
        }
    }
}

impl eframe::App for NiwoecApp {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        // ---------- Custom dark theme with blue‑outline buttons ----------
        let mut style = (*ctx.style()).clone();
        style.visuals.dark_mode = true;
        style.visuals.widgets.active.bg_stroke =
            egui::Stroke::new(1.0, egui::Color32::from_rgb(0, 150, 255));
        style.visuals.widgets.inactive.bg_stroke =
            egui::Stroke::new(1.0, egui::Color32::from_rgb(0, 100, 200));
        style.visuals.widgets.hovered.bg_stroke =
            egui::Stroke::new(2.0, egui::Color32::from_rgb(0, 200, 255));
        style.visuals.widgets.active.bg_fill = egui::Color32::TRANSPARENT;
        style.visuals.widgets.inactive.bg_fill = egui::Color32::TRANSPARENT;
        style.visuals.widgets.hovered.bg_fill =
            egui::Color32::from_rgba_premultiplied(0, 100, 255, 30);
        ctx.set_style(style);

        // ---------- Main UI ----------
        egui::CentralPanel::default().show(ctx, |ui| {
            ui.heading("N.I.W.O.E.C.");
            ui.label("Native Interface for Workload Optimisation and Experience Check");
            ui.separator();

            // ----- Host specs group -----
            ui.group(|ui| {
                ui.label("Your PC Specifications");
                ui.horizontal(|ui| {
                    ui.label(format!(
                        "CPU: {} cores @ {} MHz",
                        self.host.cpu_cores, self.host.cpu_freq_mhz
                    ));
                    ui.label(format!("RAM: {} MB", self.host.ram_mb));
                });
                ui.horizontal(|ui| {
                    ui.label("GPU VRAM (MB, manually adjustable):");
                    ui.add(
                        egui::DragValue::new(&mut self.user_gpu_vram)
                            .clamp_range(0..=128_000)
                            .speed(128),
                    );
                });
            });

            // ----- Target specs group -----
            ui.group(|ui| {
                ui.label("Target Hardware Configuration");
                ui.horizontal(|ui| {
                    ui.label("CPU Cores:");
                    ui.add(
                        egui::DragValue::new(&mut self.target.cpu_cores)
                            .clamp_range(1..=256),
                    );
                });
                ui.horizontal(|ui| {
                    ui.label("RAM (MB):");
                    ui.add(
                        egui::DragValue::new(&mut self.target.ram_mb)
                            .clamp_range(512..=1_048_576)
                            .speed(256),
                    );
                });
                ui.horizontal(|ui| {
                    ui.label("GPU VRAM (MB):");
                    ui.add(
                        egui::DragValue::new(&mut self.target.gpu_vram_mb)
                            .clamp_range(512..=48_000)
                            .speed(256),
                    );
                });
            });

            // ----- Comparison + actions -----
            let target_exceeds = self.target.cpu_cores > self.host.cpu_cores
                || self.target.ram_mb > self.host.ram_mb
                || self.target.gpu_vram_mb > self.user_gpu_vram;

            ui.horizontal(|ui| {
                if target_exceeds {
                    ui.colored_label(
                        egui::Color32::YELLOW,
                        "⚠ Target exceeds host — AI analysis required",
                    );
                } else {
                    ui.colored_label(
                        egui::Color32::GREEN,
                        "✔ Target is within your hardware capabilities",
                    );
                    if ui.button("Simulate (AI optional)").clicked() {
                        self.output_text = "Target ≤ host: app should run normally. You can still use AI for deeper analysis.".into();
                        self.output_color = egui::Color32::GREEN;
                    }
                }

                let ai_button = ui.button("🤖 AI Analyze");
                if ai_button.clicked() {
                    if let Some(path) = FileDialog::new()
                        .add_filter("Text files", &["txt"])
                        .pick_file()
                    {
                        let contents = std::fs::read_to_string(path).unwrap_or_default();
                        if contents.trim().is_empty() {
                            self.output_text = "Error: The selected file is empty.".into();
                            self.output_color = egui::Color32::RED;
                        } else {
                            if self.ai_model.is_none() {
                                self.ai_model = Some(AiModel::new());
                            }
                            if let Some(model) = &self.ai_model {
                                let (works, explanation) = model.predict(&contents, &self.target);
                                if works {
                                    self.output_text = format!("✅ Works\n{}", explanation);
                                    self.output_color = egui::Color32::GREEN;
                                } else {
                                    self.output_text = format!("❌ Doesn't work\n{}", explanation);
                                    self.output_color = egui::Color32::RED;
                                }
                            }
                        }
                    }
                }
            });

            // ----- Output box -----
            ui.separator();
            ui.group(|ui| {
                ui.heading("Result");
                if self.output_text.is_empty() {
                    ui.label("No analysis run yet.");
                } else {
                    ui.colored_label(self.output_color, &self.output_text);
                }
            });
        });
    }
}

// ------------------------------------------------------------
// 5. Application entry point
// ------------------------------------------------------------
fn main() {
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_inner_size([640.0, 520.0])
            .with_min_inner_size([550.0, 450.0]),
        ..Default::default()
    };
    eframe::run_native(
        "N.I.W.O.E.C.",
        options,
        Box::new(|_cc| Box::<NiwoecApp>::default()),
    )
    .unwrap();
}
