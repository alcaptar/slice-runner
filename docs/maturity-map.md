# Mapa de madurez: dónde encaja nuestro pipeline

> **Lectura fechada, no vara de medir.** Situa el repo en un modelo externo con los datos del
> 2026-07-16. No se actualiza: donde diga en que escalon estamos, dice donde estabamos entonces.

Referencia: **"Steps of AI Adoption"**, Boris Cherny (2026-07-16). Modelo de 5 escalones (0 Gated → 4 AI-native) por rol, nº de agentes, cuello de botella, productos y guardrails. Este doc sitúa `slice-runner`/la skill de seguimiento de despliegues en ese mapa.

## Los escalones (resumen)

| Step | Rol | Agentes | Cuello de botella |
|---|---|---|---|
| 0 Gated | — | 0 | Procesos legacy de seguridad/aprobación |
| 1 Assisted | tú + 1 agente (pair) | ~1 | Tu atención: revisas cada cambio |
| 2 Parallel | orquestador | ~10 | Revisar output (varios streams) |
| 3 Supervised autonomy | manager of managers | ~100 | Confianza en el loop + throughput de decisión + eficiencia de tokens |
| 4 AI-native | VP por intención | ~1000+ | Identificar y automatizar trabajo a escala con los guardrails correctos |

## Dónde estamos

**Step 1 → construyendo la rampa al Step 2.** `slice-runner` Nivel 1 es exactamente "un agente, supervisado, revisas antes de mergear".

## Nuestro diseño = el checklist 1→2→3 de Cherny

| "Para subir de nivel" (Cherny) | Pieza nuestra |
|---|---|
| self-verification loop you trust (tests+build+lint+e2e) | controles objetivos + verificador (1→2) |
| automate code review | verificador independiente (escritor≠verificador) |
| run more than one agent, worktree isolation | Nivel 3 (Workflow fan-out + worktrees) |
| loops and routines (`/loop` `/goal` `/batch`) | Nivel 2 |
| let Claude kick off Claude | encadenado slice-runner → seguimiento de despliegues |
| CLAUDE.md and Skills to encode standards | jerarquía de convenciones del repo |
| manage token use; monitoring (OTel/Analytics) | presupuesto por slice + estado/seguimiento en el issue de GitHub |

## El aviso clave

El cuello de botella se desplaza: atención (1) → revisar output (2) → **confianza en el loop** (3). La trampa, en palabras de Cherny: *"scaling agent count before the loop has earned widespread trust."* Coincide con el research (los proyectos fallan por falta de patrones, no por el modelo) y con nuestro principio: **subir de nivel solo cuando el anterior sea fiable.**

## Implicación estratégica

Cherny lista productos oficiales por escalón: Auto mode, Agent view, `/loop` `/batch` `/goal`, Routines, **Claude Code Review**, **Claude Security Review**, worktree isolation, Agent SDK, sandboxing. Confirma la conclusión del research: **la mecánica del loop es commodity — usarla de fábrica**. El trabajo custom se justifica solo en el moat:

1. **Verificador consciente de las convenciones del repo** (hexagonal/DDD, la vara de cada capa) — aporta sobre el Claude Code Review genérico.
2. **la skill de seguimiento de despliegues** con la observabilidad que ya tenga el repo.

Todo lo demás (orquestación, worktrees, routines, review genérico, sandboxing) conviene apoyarlo en los primitivos oficiales en vez de re-implementarlo.

## Siguiente paso hacía Step 2

Cerrar el "self-verification loop you trust": validar el verificador en runs reales hasta ganarle confianza, y solo entonces activar Nivel 2 (`/loop` con presupuesto + circuit breaker por intentos). No aumentar el nº de agentes antes.
