# Loops autónomos de agentes de código: qué se ha descubierto

> **Bibliografia, no vara de medir.** Resume lo que otros han publicado y medido, con sus fuentes.
> No describe este repo ni lo gobierna; se cita desde las notas de diseño de entonces cuando una decisión se
> apoya en algo de aquí.

Research sobre el estado del arte de los loops autónomos para el flujo **spec -> slice -> implementar -> PR -> CI verde**. Cubre cuatro dimensiones: resultados y lecciones reales, verificación y calidad, coste y economía, y seguridad y guardrails; más una comparativa de frameworks.

## Nota metodológica (leer primero)

- Generado con un harness de deep research (fan-out de búsquedas -> fetch de ~35 fuentes -> extracción de 125 claims). **La fase de verificación adversarial (3 votos por claim) se detuvo por coste**, así que los claims están *fundamentados en fuente pero no cross-verificados* por el harness. La síntesis y el filtrado de solidez los hice manualmente.
- **Confianza por claim**, marcada así:
  - `[fuerte]` — fuente primaria (paper arXiv, estudio, doc oficial) o coincidencia de varias fuentes independientes.
  - `[media]` — blog técnico serio, razonamiento coherente, pero fuente única.
  - `[anecdótico]` — caso puntual auto-reportado, sin datos reproducibles; útil como señal, no como prueba.
- Sesgo de fuentes: predominan posts de 2026 del movimiento "loop engineering" y de la comunidad Ralph. Hay pocos estudios controlados; los que hay (Stanford, METR, TDFlow, TDAD) pesan más.

## TL;DR

1. **El cuello de botella no es generar código, es verificarlo.** `[fuerte]` Es el consenso transversal más claro. Toda la ingeniería de valor está en los gates, no en el loop.
2. **Escritor != verificador** es el patrón dominante de calidad: un segundo agente (o persona) con instrucciones distintas juzga, porque el que escribe se aprueba a sí mismo con demasiada indulgencia. `[fuerte]`
3. **La calidad de la spec es la palanca principal.** La ambigüedad se multiplica en loops; specs vagas hacen fracasar cualquier workflow. `[fuerte]`
4. **Los loops baratos existen y a veces son espectaculares** (MVPs por cientos de $), pero el coste es **muy impredecible** (hasta 30x de varianza en la misma tarea) y los casos de éxito son anecdóticos. `[media/anecdótico]`
5. **Pasar los tests no es suficiente para mergear.** ~la mitad de los parches que pasan SWE-bench no los mergearía un maintainer real. `[fuerte]`
6. **Los guardrails que importan** son circuit breakers (no solo kill switch), aislamiento (worktrees + runtime + contenedor), arranque read-only y control humano del "outer loop". `[fuerte]`

---

## Qué es un loop de agente de código

Un loop autónomo sustituye a la persona como *prompter* del agente: un sistema que **arranca, persigue un objetivo verificable, usa herramientas y memoria, evalúa el progreso e itera hasta una condición de parada** ([Addy Osmani, Loop Engineering](https://addyosmani.com/blog/loop-engineering/)). El ciclo canónico es **assess -> act -> verify -> stop**.

Osmani estructura el loop en **cinco primitivas + estado externo** `[fuerte, multi-fuente]`:
- **Automations** (descubrimiento programado), **Worktrees** (aislamiento paralelo), **Skills** (conocimiento del proyecto en `SKILL.md`), **Plugins/Connectors** (MCP), **Subagents** (verificación independiente), y **External State** (markdown/tablero que registra progreso: "el agente olvida, el repo no").

Distinción clave de Osmani: **inner loop vs outer loop**. Los agentes corren el inner loop (investigar, implementar, verificar) de forma autónoma; los humanos deben ser dueños del **outer loop** (verificación de calidad, veredicto ship/block, responsabilidad). Delegar el outer loop es *"abdicación con buenas herramientas"* `[media]` ([Osmani](https://addyosmani.com/blog/loop-engineering/)).

---

## Dimensión 1 — Resultados y lecciones reales

### Casos de éxito (mayormente anecdóticos)
- Un **MVP valorado en ~$50k se entregó (testeado y revisado) por $297** con Ralph + Amp. `[anecdótico]` ([ghuntley.com/ralph](https://ghuntley.com/ralph/))
- Un proyecto **spec -> implementación completo en ~16 runs / ~4 horas por ~70 €** de coste de API. `[anecdótico]` ([codecentric](https://www.codecentric.de/en/knowledge-hub/blog/the-ralph-wiggum-loop-autonomous-code-generation-with-a-fresh-context))
- Huntley afirma haber conseguido **self-healing autónomo** (detectar, estudiar, arreglar, desplegar y verificar), pero **sin aportar cifras** de tokens ni $. `[anecdótico]` ([ghuntley.com/loop](https://ghuntley.com/loop/))

### Casos de fracaso (las lecciones más valiosas)
- **PR-babysitter sin límites: 43 commits en un día**, scope-creep a áreas no relacionadas, deriva del propósito del PR y **casi todo el output rechazado**. El fallo emblemático del loop no acotado. `[media]`
- **Loop nocturno sin supervisión (11 PM–7 AM)**: miles de tool-calls idénticos, **$437 de factura** sin intervención automática. `[media]` ([dev.to/waxell](https://dev.to/waxell/ai-agent-circuit-breakers-the-reliability-pattern-production-teams-are-missing-5bpg))
- **"90% de proyectos de agentes fallan"**, atribuido a patrones ausentes (límites, verificación) más que al modelo. `[media]` ([dev.to/thedailyagent](https://dev.to/thedailyagent/why-90-of-ai-agent-projects-fail-and-the-patterns-that-fix-it-1dma))

### Datos duros sobre capacidad
- **La tasa de éxito cae en picado con la complejidad**: ~100% en tareas de <4 min para un humano, **<10% en tareas de >4 h** (citando METR 2025). `[fuerte]`
- **Pasar tests aislados no basta para mergear**: METR halló que **~la mitad** de los parches que pasan SWE-bench no los mergearía un maintainer real; un estudio de **33k PRs de agentes** señala fallos de CI/CD y regresiones como causas top de rechazo. `[fuerte]` ([TDAD, arXiv](https://arxiv.org/pdf/2603.17973))
- **Correlación con degradación de calidad**: código copy-paste subió de 8.3% a 12.3% y el refactor bajó de 25% a <10% (citando GitClear 2025). `[media]`

**Lección central:** el modo de fallo dominante es **mala planificación / spec ambigua**, no mala capacidad de codificar. Los loops que funcionan descomponen en tareas pequeñas y hacen **una sola cosa por iteración**. `[fuerte, multi-fuente]`

---

## Dimensión 2 — Verificación y calidad

### Escritor != verificador (split authorship)
Consenso transversal: el modelo que escribe el código **lo aprueba con demasiada indulgencia**; hace falta un segundo agente con instrucciones (y a veces modelo) distintas. `[fuerte, multi-fuente]` ([Osmani](https://addyosmani.com/blog/loop-engineering/), [aibuilderclub](https://www.aibuilderclub.com/blog/loop-engineering-addy-osmani)). Matiz importante: **ese verificador se convierte en el cuello de botella de throughput** — es donde está el trabajo real.

Evidencia académica de que separar roles funciona:
- **TDFlow** (writer / debugger / reviser como sub-agentes separados) alcanza **88.8% en SWE-Bench Lite** (+27.8 pp sobre el mejor baseline) y **94.3% en Verified** con tests escritos por humanos; quitar el sub-agente de debugging baja de 94.3% a 87.2%. `[fuerte]` ([TDFlow, arXiv](https://arxiv.org/pdf/2510.23761))

### TDD, red-green-refactor y sus trampas
- Con agentes, el **TDD test-first se vuelve casi obligatorio** para evitar que el agente "juegue" con tests que pasan mientras la implementación diverge. `[media]`
- Pero los agentes **derivan sistemáticamente hacía "big bang" test-first** (generan muchos tests de golpe y luego implementan), saltándose el ciclo red-green. Herramientas como **tdd-guard** lo fuerzan con un hook + un "juez" IA separado (otra vez writer != verifier). `[media]` ([brgr.one](https://www.brgr.one/blog/ai-coding-agents-tdd-enforcement))
- Coste de forzar TDD: **~duplica el tiempo** y sube tokens, a cambio de mejor calidad de asserts y adherencia arquitectónica. `[media]`
- **Paradoja del prompting de TDD** `[fuerte]`: en modelos pequeños, añadir instrucciones procedimentales de TDD **sin** contexto de tests empeoró los resultados (regresiones +42%). Lo que ayuda es **surfacing de contexto** (qué tests están en riesgo), no prescribir el workflow: el enfoque TDAD redujo regresiones **un 70%** (6.08% -> 1.82%) dándole al agente análisis de impacto. ([TDAD, arXiv](https://arxiv.org/pdf/2603.17973))

### Refactor y hardening
- **VSDD** (Verified Spec-Driven Development) mandata red-green-refactor estricto (refactor solo tras verde) y una fase de **"Formal Hardening"** con mutation testing (mutmut, Stryker), property-based (Hypothesis) y fuzzing; el verificador es un revisor adversarial en contexto fresco para evitar el sesgo de "goodwill acumulado". `[media]` ([VSDD gist](https://gist.github.com/dollspace-gay/d8d3bc3ecf4188df049d7a4726bb2a00))
- **Crítica válida (no todo es consenso):** un revisor senior objetó que la premisa de VSDD de "spec hermética antes de construir" reproduce el fallo de waterfall — los edge cases no se pueden enumerar antes de implementar, porque **implementar es en sí un proceso de descubrimiento**. `[media]`

### La palanca real: la spec
**La calidad de la especificación es el punto de mayor apalancamiento** en el camino spec->producción, porque la ambigüedad se compone a través de los workstreams paralelos. `[fuerte, multi-fuente]` Requisito recurrente: spec con **lista de tareas checkeable** y **una tarea por iteración**.

---

## Dimensión 3 — Coste y economía

- **Las tareas agénticas consumen ~1000x más tokens** que el "code chat/reasoning", y **el coste lo dominan los tokens de input**, no de output. `[fuerte]` (Stanford Digital Economy Lab, [enlace](https://digitaleconomy.stanford.edu/publication/how-do-ai-agents-spend-your-money-analyzing-and-predicting-token-consumption-in-agentic-coding-tasks/))
- **El coste es muy impredecible**: repetir la misma tarea puede variar **hasta 30x** en tokens; los LLMs frontera **no saben estimar su propio consumo** (correlaciones ≤0.39) y lo **subestiman** sistemáticamente. La dificultad percibida por expertos correlaciona mal con el coste real. `[fuerte]` (Stanford)
- **Economía de retry stateless**: para ciertas clases de tarea, los loops sin estado son económicamente superiores porque los tokens son baratos frente a la mano de obra (ej. un bugfix nocturno de $5 vs $100/h de un dev). `[media]` ([redreamality](https://redreamality.com/blog/ralph-wiggum-loop-vs-open-spec/))
- **Métrica correcta: "coste por outcome aceptado"** (coste de sesión / outcomes aceptados), no el gasto bruto en tokens. Una sesión cara que produce un cambio correcto, testeado y durable puede ser más coste-eficiente que muchas baratas que se descartan. `[media]` ([larridin](https://larridin.com/developer-productivity-hub/token-cost-effectiveness-ai-coding))

**Lectura para autonomía:** la autonomía compensa cuando (a) la tarea es pequeña y verificable, (b) el gate de verificación es fiable, y (c) mides coste-por-outcome-aceptado. Sin (b), escalas gasto impredecible sin garantía de merge.

---

## Dimensión 4 — Seguridad y guardrails

### Circuit breaker != kill switch
- **Circuit breaker**: para al agente *autónomamente* en pleno fallo. **Kill switch**: requiere intervención humana *después* de que algo ya salió mal. Necesitas el primero. `[media]` ([dev.to/waxell](https://dev.to/waxell/ai-agent-circuit-breakers-the-reliability-pattern-production-teams-are-missing-5bpg))
- Disparadores recomendados: **2-3 tool-calls idénticos sin progreso** (runaway), **3 fallos consecutivos** en la misma operación, **umbrales coste-velocidad** ($50/h, $200/sesión) y **violaciones de scope** (acceso a fuentes no permitidas). `[media]`
- Ralph implementa un circuit breaker simple: cada spec cuenta intentos y **tras 10 se marca "stuck"**; además, guardrails en texto plano (`.ralph/guardrails.md`) donde se anexan "señales" tras fallos, que los agentes frescos heredan. `[media]` ([github ralph-wiggum](https://github.com/fstandhartinger/ralph-wiggum))
- Aviso: **el observability pasivo (LangSmith, Helicone, Langfuse) no basta** — registra post-hoc, no hace enforcement en tiempo real. `[media]`

### Aislamiento y blast radius
- **Worktrees** son ya un primitivo estructural (no una comodidad) por los agentes paralelos, pero **aíslan estado de código, no de ejecución**: ramas paralelas colisionan en runtime (puertos, DBs, `.env`, estado de browser). Hay que aislar también el entorno de ejecución. `[fuerte]` ([penligent](https://www.penligent.ai/hackinglabs/git-worktrees-need-runtime-isolation-for-parallel-ai-agent-development/))
- **Contenedores** como control principal de blast radius: agentbox restringe el acceso del agente al directorio del proyecto y monta explícito; el host y otros proyectos quedan inalcanzables. El rollback se apoya en **git (`git reset --hard`)**. `[media]` ([agentbox](https://github.com/scharc/agentbox))
- Principio: diseñar para que **el blast radius quede acotado aunque un ataque tenga éxito** (p. ej. prompt injection), en vez de asumir que el aislamiento previene todo ataque. `[media]`
- Empezar **read-only** y conceder escritura solo cuando los checks puedan rechazar output; **service accounts y least privilege**, nunca credenciales humanas reusadas; **secretos y credenciales de deploy fuera** de cualquier contexto que el agente pueda leer. `[fuerte, multi-fuente]`

### El humano y el "outer loop"
- **Las aprobaciones por paso degeneran en rubber-stamping** y dejan de ser un control real; los agentes actúan en runtime eligiendo acciones dinámicamente, así que el oversight por-paso **no escala**. Mejor: límites de tarea estrechos + criterios de terminación explícitos + revisión en el punto correcto (el PR/diff), no en cada acción. `[fuerte]` ([nhimg.org](https://nhimg.org/community/agentic-ai-and-nhis/ai-agent-approvals-and-alert-fatigue-what-teams-are-missing/))
- Dato de gobierno: solo **52%** de las empresas puede auditar qué datos tocan sus agentes; **48%** tiene un punto ciego total. `[media]`

### Riesgos "blandos" (Osmani)
Tres deudas compuestas de los loops autónomos: **intent debt** (el agente rellena contexto ausente con suposiciones confiadas), **comprehensión debt** (el código se envía más rápido de lo que el equipo lo lee), y **cognitive surrender** (aceptar outputs sin escrutinio). `[media]` ([Osmani](https://addyosmani.com/blog/loop-engineering/))

---

## Comparativa de frameworks

| Framework | Enfoque | Ventajas | Inconvenientes |
|---|---|---|---|
| **Ralph loop** (Huntley) | Bash loop que reinicia el agente con **contexto fresco** cada iteración; 1 tarea/run; estado en ficheros + git; `<promise>DONE</promise>` como sentinel | Simplísimo, barato, evita degradación de contexto, agent-agnóstico (Claude Code/Cursor/Codex) | No determinista (puede generar placeholders/código roto); **exige experto senior**; guardrails mínimos; "at your own risk" `[media]` |
| **Claude Code** (`/loop`, `/goal`, background agents, subagents) | Loop con condición de parada (`/goal`), agentes en background, subagentes para verificación, worktrees | Verificación integrable (writer!=verifier), worktrees, skills, ecosistema maduro | Coste de subagentes paralelos; requiere diseñar los gates uno mismo `[media]` |
| **OpenAI Codex** | Loop con instrucciones de repo + verificación por terminal/comandos locales | Bueno cuando importan comandos locales y verificación en terminal; worktrees | Menos orquestación de alto nivel `[media]` |
| **GitHub Copilot Coding Agent** | Issue -> PR autónomo | Encaja en flujo GitHub issue->PR | Menos control fino; requiere tests+diff review+rollback obligatorios `[media]` |
| **Cursor Background Agents** | Ejecución en background dentro de Cursor | Bueno si el equipo ya vive en Cursor | Atado al IDE `[media]` |
| **GitHub Spec Kit** | SDD estructurado (constitution.md, specs con AC) | Requisitos claros upfront; estándar | Lento (una build web ~90 min en un test); flojo en cambios iterativos pequeños `[anecdótico]` |
| **BMAD** | SDD pesado, multi-rol | Muy estructurado | Muy lento (5.5–8 h en el mismo test); pesado `[anecdótico]` |
| **GSD** | Meta-prompting SDD con gestión de contexto por "waves" | Manejo de contexto | Menos evidencia pública `[media]` |
| **OpenSpec** | SDD con **formato delta** (ADDED/MODIFIED/REMOVED) | **Único pensado para cambios iterativos pequeños**; rápido (7–12 min en el test) | Menos maduro/ecosistema `[anecdótico]` |

Notas transversales `[media]`:
- Los SDD caen en un espectro: **Spec-First** (spec se descarta) -> **Spec-Anchored** (persiste y evoluciona) -> **Spec-as-Source** (solo se edita la spec, el código se genera). ([cameronsjo/spec-compare](https://github.com/cameronsjo/spec-compare))
- Huntley defiende que la **complejidad multi-agente suele ser innecesaria y contraproducente** (agentes no deterministas como microservicios = caos); prefiere un único loop monolítico. Contrasta con TDFlow, donde separar sub-agentes sí mejoró resultados en benchmark — probablemente depende de si los roles están bien acotados. ([ghuntley.com/loop](https://ghuntley.com/loop/))

---

## Síntesis para nuestro pipeline (slice-runner / seguimiento de despliegues)

Qué **valida** lo que ya construimos:
- Slices pequeñas / una cosa por iteración; spec como fuente de verdad y estado; escritor != verificador; controles objetivos (lint/types/tests/CI); refactor tras verde; convenciones del repo como vara. Todo aparece como patrón recurrente y/o con respaldo académico.
- Control humano en merge y rollback = el "outer loop" de Osmani.

Qué **sugiere ajustar / vigilar**:
1. **El verificador es el cuello de botella y el sitio donde está el valor** — invertir ahí, no en generar más rápido. Coincide con el reenfoque que ya hicimos (revisión de convenciones/arquitectura, no re-testeo).
2. **CI verde no es suficiente**: ~50% de parches que pasan tests no son mergeables. Refuerza que el gate de convenciones/arquitectura del verificador es imprescindible, no opcional.
3. **Coste impredecible (30x)**: para el Nivel 2 (`/loop`), añadir **presupuesto de tokens/$** como circuit-breaker además de `max_consecutive_failures` y `max_runtime`. Medir **coste por slice aceptada (mergeada)**, no por slice intentada.
4. **Aislamiento runtime, no solo worktree**: para el Nivel 3 (paralelo), el `COMPOSE_PROJECT_NAME`/puertos por worktree que ya anotamos es exactamente el gap "código aislado != ejecución aislada".
5. **Circuit breaker con contador de intentos por slice** (estilo Ralph: marcar "stuck" tras N) encaja con nuestro `[!]` de slice bloqueada.
6. **Cuidado con intent/comprehensión debt y rubber-stamping**: el gate de check-alignment y leer los outputs a propósito son la contramedida.

---

## Fuentes

**Loop engineering / marco general**
- [Loop Engineering — Addy Osmani](https://addyosmani.com/blog/loop-engineering/) · [The Factory Model — Osmani](https://addyosmani.com/blog/factory-model/) · [Self-Improving Coding Agents — Osmani](https://addyosmani.com/blog/self-improving-agents/)
- [Loop Engineering — O'Reilly Radar](https://www.oreilly.com/radar/loop-engineering/) · [Addy Osmani's Loop Engineering: The 5 Components — aibuilderclub](https://www.aibuilderclub.com/blog/loop-engineering-addy-osmani) · [What Is Loop Engineering? — smartscope](https://smartscope.blog/en/generative-ai/methodology/loop-engineering-agent-loops-2026/) · [LangChain](https://www.langchain.com/)

**Ralph loop**
- [Ralph Wiggum as a "software engineer" — Huntley](https://ghuntley.com/ralph/) · [everything is a ralph loop — Huntley](https://ghuntley.com/loop/) · [The Ralph Wiggum Loop — codecentric](https://www.codecentric.de/en/knowledge-hub/blog/the-ralph-wiggum-loop-autonomous-code-generation-with-a-fresh-context) · [What Is the Ralph Loop? — Wiggum CLI](https://wiggum.app/blog/what-is-the-ralph-loop/) · [ralph-wiggum.ai](https://ralph-wiggum.ai/) · [fstandhartinger/ralph-wiggum (GitHub)](https://github.com/fstandhartinger/ralph-wiggum)

**Verificación y calidad**
- [TDAD (Test-Driven Agentic Development) — arXiv](https://arxiv.org/pdf/2603.17973) · [TDFlow — arXiv](https://arxiv.org/pdf/2510.23761) · [Productivity-Reliability Paradox — arXiv](https://arxiv.org/pdf/2605.01160) · [tdd-guard — brgr.one](https://www.brgr.one/blog/ai-coding-agents-tdd-enforcement) · [VSDD — gist](https://gist.github.com/dollspace-gay/d8d3bc3ecf4188df049d7a4726bb2a00) · [Spec + TDD — Augment Code](https://www.augmentcode.com/guides/spec-tdd-shippable-ai-generated-code)

**Coste y economía**
- [How Do AI Agents Spend Your Money? — Stanford Digital Economy Lab](https://digitaleconomy.stanford.edu/publication/how-do-ai-agents-spend-your-money-analyzing-and-predicting-token-consumption-in-agentic-coding-tasks/) · [AI Coding Costs 2026 — morphllm](https://www.morphllm.com/ai-coding-costs) · [Token Cost Effectiveness — larridin](https://larridin.com/developer-productivity-hub/token-cost-effectiveness-ai-coding) · [6 Strategies for Managing Token Costs — exceeds.ai](https://blog.exceeds.ai/ai-coding-token-costs-2026/)

**Seguridad y guardrails**
- [AI Agent Circuit Breakers — dev.to/waxell](https://dev.to/waxell/ai-agent-circuit-breakers-the-reliability-pattern-production-teams-are-missing-5bpg) · [Build AI Agents That Fail Safely — dev.to/the_bookmaster](https://dev.to/the_bookmaster/how-to-build-ai-agents-that-fail-safely-circuit-breakers-health-checks-and-graceful-degradation-1dce) · [agentbox — GitHub](https://github.com/scharc/agentbox) · [Git Worktrees Need Runtime Isolation — penligent](https://www.penligent.ai/hackinglabs/git-worktrees-need-runtime-isolation-for-parallel-ai-agent-development/) · [AI Agent Approvals and Alert Fatigue — nhimg](https://nhimg.org/community/agentic-ai-and-nhis/ai-agent-approvals-and-alert-fatigue-what-teams-are-missing/) · [Why 90% of AI Agent Projects Fail — dev.to/thedailyagent](https://dev.to/thedailyagent/why-90-of-ai-agent-projects-fail-and-the-patterns-that-fix-it-1dma)

**Comparativa de frameworks / SDD**
- [Spec-Driven Development e AI Agent Loop — Dispenza](https://www.davidedispenza.com/en-us/blog/agent-spec-driven-development) · [spec-compare — cameronsjo (GitHub)](https://github.com/cameronsjo/spec-compare) · [Copilot vs Codex vs Cursor Background Agents — ralphable](https://ralphable.com/blog/copilot-coding-agent-vs-codex-vs-cursor-background-agents-2026) · [Ralph Wiggum Loop vs Open Spec — redreamality](https://redreamality.com/blog/ralph-wiggum-loop-vs-open-spec/) · [BMAD vs GitHub Spec Kit — Sabaliauskas](https://medium.com/@mariussabaliauskas/a-comparative-analysis-of-ai-agentic-frameworks-bmad-method-vs-github-spec-kit-edd8a9c65c5e) · [Spec-Driven Development Guide (BMAD, GSD, Ralph) — Pillitteri](https://pasqualepillitteri.it/en/news/158/framework-ai-spec-driven-development-guide-bmad-gsd-ralph-loop)

---

*Limitación: informe basado en la fase de recopilación del deep research (la verificación adversarial no se ejecutó). Los claims `[anecdótico]` deben tratarse como señales, no como pruebas. Fecha: 2026-07-17.*
