# ML subsystem

The first model task is UI element classification. Only train from reviewed, labelled observations. Raw browser observations are not ground truth.

Pipeline: collect DOM/accessibility features → human/oracle labels → versioned dataset → website-grouped train/test split → baseline classifier → macro F1/per-class metrics → held-out website evaluation → model registry promotion gate.

Planned tasks: element classification, locator ranking, workflow scoring, failure classification, flaky-test risk, defect similarity and visual anomaly detection.
