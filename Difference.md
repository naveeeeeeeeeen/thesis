# Comprehensive Guide: SBP Algorithm, TCHES 2025 Framework, and Integration Strategies

---

## PART A: The SBP Paper — "Optimizing Implementations of Linear Layers Using Two and Higher Input XOR Gates"

### A1. Layman Terms (The Big Picture)

#### The Problem: The "Blender" of Cryptography
In block ciphers (like AES), there is a component called the **Linear Layer** (or Diffusion Layer). Think of it as a "blender" that mixes the data bits together so that a tiny change in the input completely changes the output. In hardware, this blending is done using **XOR gates**. 
* **The Catch:** XOR gates cost money, take up space (Area/GE), and take time to compute (Latency/Depth). Cryptographers want to build this "blender" using the absolute minimum number of XOR gates and in the fewest number of sequential steps (Depth).

#### The Old Way: Boyar-Peralta (BP) Algorithm
To find the shortest sequence of XOR operations (called a Straight-Line Program or SLP), researchers use the BP heuristic. Imagine trying to build a specific Lego castle using the fewest blocks. The BP algorithm is like a greedy builder: at every step, it looks at all possible pairs of blocks it can snap together, and it *always* picks the pair that creates the most "useful" new shape. 
* **The Flaw:** Because it is too greedy, it often gets trapped in a "dead end" (local optimum). Furthermore, it doesn't care about the *height* of the castle (Circuit Depth). It might build a castle that uses few blocks but is 10 stories tall (high latency).

#### The New Way: SBP (Superior Boyar-Peralta)
The authors created SBP to fix the BP algorithm's flaws. Instead of blindly picking the single best move, the SBP builder says: *"Let me find the Top 5 best moves I can make right now. Then, I will roll a dice and pick one of those 5."*
* **Why this works:** By keeping a shortlist of the best options and picking randomly among them, SBP avoids dead-ends while still moving in a generally excellent direction.
* **Depth Awareness:** SBP also has a "ruler." It refuses to make a move if it makes the castle taller than a specific limit (e.g., Depth 3).

### A2. Standard / Technical Explanation

#### 1. Background & Metrics
The paper focuses on optimizing MDS (Maximum Distance Separable) matrices. The cost is measured by:
* **g-XOR (general-XOR):** The minimum number of 2-input XOR gates required, allowing temporary intermediate variables.
* **Circuit Depth:** The longest path from input to output (Latency).
* **GE (Gate Equivalent):** The actual silicon area in specific ASIC libraries.

#### 2. The Core of SBP: How it Works
SBP improves upon the standard BP algorithm by modifying how candidate signals are selected through **Threshold-based Candidate Pooling** and **Depth-Bounding**.
1. **Depth Limit Enforcement:** Before evaluating a pair, SBP checks their depths. If adding a new gate exceeds the `depthLimit`, it skips them.
2. **The `chosenParam` Threshold:** Instead of taking the absolute global minimum distance reduction, SBP maintains an array of size `chosenParam`. As it scans pairs, if a pair yields a distance reduction that is better than or equal to the current best, it is added to the array. If the array exceeds `chosenParam`, it overwrites the oldest entries (acting as a circular buffer). This acts as a **Top-K Elite Pool**.
3. **Randomized Selection:** Once the scan is complete, SBP uses a Uniform Integer Distribution to randomly pick one pair from the Top-K pool.

### A3. Example Walkthrough (The GH1 Matrix)
The paper introduces a new 4x4 Involutory MDS matrix over F_2^4 named GH1. 
* **Previous Best:** 45 g-XORs (Depth 3).
* **SBP Result:** 41 g-XORs (Depth 3).
By utilizing the Top-K pool and depth bounding, SBP successfully navigates the search space to find highly reusable intermediate signals (like $t_8 = t_6 \oplus t_7$ at Depth 3) that perfectly match target outputs without exceeding the latency constraint, saving 4 XOR gates compared to the previous state-of-the-art.

---

## PART B: The TCHES 2025 Paper — "A Framework for Generating S-Box Circuits with Boyar–Peralta Algorithm-Based Heuristics"

### B1. Core Concepts of the TCHES Framework
The TCHES paper shifts the focus from purely linear layers to **S-Box circuits**, which contain interleaved XOR and non-linear (AND/OR) gates. 
* **Pre-emptive Strategy:** If the inputs to an AND/OR gate are already computed in the base, the algorithm forces the AND/OR gate immediately, bypassing the XOR competition loop.
* **Distance Metric with Infinity:** Because targets might be blocked by uncomputed AND gates, distances can be Infinity ($\infty$). The algorithm must explicitly filter out $\infty$ before calculating norms.
* **RNBP (Random Normal BP):** Collects *every single pair* that ties for the best score (minimum distance sum, maximum Euclidean norm) and picks randomly.
* **BPD (BP with Depth limit):** Uses target-specific depth limits ($H_Y$) rather than a global limit, which is much more accurate for the varied structures of S-boxes.

---

## PART C: How SBP Differs from TCHES's RNBP/BPD

| Feature | SBP (Paper 1) | RNBP / BPD (TCHES Paper 2) |
| :--- | :--- | :--- |
| **Target Domain** | **Linear Layers** (Matrices, XOR gates only). | **S-Box Circuits** (Interleaved XOR and AND/OR gates). |
| **Tie-Breaking Pool** | **Top-K Pool (`chosenParam`)**: Maintains a fixed-size circular buffer of the best candidates. | **All-Ties Pool**: Scans all pairs, collects *every single pair* that ties for the best score, and picks randomly. |
| **Distance Metric** | Distances are always **finite**. | Distances can be **$\infty$**. Must explicitly filter out $\infty$ before calculating norms. |
| **Non-Linear Gates** | Not applicable. | Uses a **Pre-emptive Strategy**: Forces AND/OR gates immediately if inputs are ready. |
| **Depth Limiting** | Uses a **Global** `depthLimit`. | Uses **Target-Specific** depth limits ($H_Y$), much more accurate for S-boxes. |

### The "Secret Sauce": Why SBP's Top-K Pool Reduces XOR Count
You might wonder: *"If RNBP already picks randomly among the best ties, how does SBP's Top-K pool improve the XOR count?"*
The answer lies in **Search Space Bias and Reusable Temporaries**.

**A Solid Example:**
Imagine you need to compute targets and evaluate pairs. You find **50 pairs** that tie for the exact best score (Sum=2, Norm=2.0).
* **RNBP Behavior:** It collects all 50 pairs and picks one with a 2% probability. Some of these 50 pairs might be combinations of primary inputs that are "dead ends" (hard to reuse later). RNBP treats them equally, leading to a blind lottery that often generates redundant XOR gates later.
* **SBP Behavior:** SBP limits the pool to `chosenParam` (e.g., 7). Because the algorithm evaluates pairs in a specific order (e.g., iterating through the base array), the circular buffer will naturally favor pairs that appear early or late in the traversal. If you order your base array to prioritize **recently generated temporaries**, SBP's Top-K pool will heavily bias the selection towards **reusing shared subexpressions**. Reusing temporaries is the mathematical key to minimizing the global XOR count.

---

## PART D: Actionable Guide to Integrate SBP into the TCHES Framework (NO CODE)

To reduce the XOR count in the TCHES paper's results, do not replace the entire algorithm. Keep the TCHES paper's S-box handling and swap the RNBP tie-breaking mechanism with SBP's Top-K pooling.

### Step 1: KEEP the TCHES Pre-emptive Strategy
Before running any XOR competition, check if any AND/OR gate can be fired. If the inputs to a non-linear gate are present in the base and their depths satisfy the target-specific limits, compute the AND/OR gate immediately and add it to the base. Bypass the XOR loop entirely for that iteration.

### Step 2: KEEP TCHES Depth and Infinity Handling
* Use the target-specific depth limits ($H_Y$) to filter out pairs that would exceed the latency constraint.
* When calculating the distance vector for a new XOR pair, explicitly filter out any targets that currently have a distance of Infinity ($\infty$) before calculating the Sum and Euclidean Norm.

### Step 3: CHANGE the Tie-Breaking Logic (Inject SBP's Top-K Pool)
Instead of collecting all ties into a massive list, implement a bounded circular buffer logic:
1. **Initialize:** Create a fixed-size array (the pool) with a capacity equal to your `chosenParam` (e.g., 7). Set up a counter, a minimum distance sum, and a maximum Euclidean norm.
2. **Iterate:** Loop through all valid signal pairs in the base.
3. **Evaluate:** Calculate the distance sum and Euclidean norm for the new pair (ignoring infinities).
4. **Update Pool:**
   * If the new sum is *strictly less* than the current minimum: Reset the counter to 0, update the minimum sum and maximum norm, and place the pair at the start of the pool.
   * If the new sum *equals* the minimum but the norm is *better*: Update the maximum norm and add the pair to the pool.
   * If it ties both sum and norm: Simply add the pair to the pool.
   * **Crucial SBP Step:** If the counter exceeds the `chosenParam` limit, wrap around using modulo arithmetic (overwrite the oldest entry in the circular buffer).
5. **Select:** After checking all pairs, use a uniform random distribution to select exactly one pair from the populated pool and add its XOR result to the base.

### Step 4: Tuning the `chosenParam`
* **For S-Boxes (like AES, Saturnin):** Keep `chosenParam` relatively low (e.g., 5 to 15). The search space is highly constrained by the non-linear gates; you want to exploit the best moves and bias towards reusing recent temporaries.
* **Warning:** If `chosenParam` is set too high, the algorithm degrades into a random walk, losing the bias toward reusable signals and potentially taking too long to converge.

### Summary Checklist for your Implementation:
1. [ ] **KEEP**: TCHES's Pre-emptive Strategy for AND/OR gates.
2. [ ] **KEEP**: TCHES's Target-Specific Depth Limits ($H_Y$).
3. [ ] **KEEP**: TCHES's $\infty$ filtering before norm calculation.
4. [ ] **CHANGE**: Replace RNBP's "Collect All Ties" with **SBP's `chosenParam` Circular Buffer**.
5. [ ] **OPTIMIZE**: Order your base array evaluations so that recently generated intermediate temporaries are evaluated first/last, allowing the circular buffer to naturally bias the Top-K pool toward highly reusable signals.