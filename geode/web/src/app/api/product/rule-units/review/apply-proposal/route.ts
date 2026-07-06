import { spawnSync } from "node:child_process";

import { getRuleUnitApplyProposalSummary } from "@/lib/product/productIndex";
import { REPOSITORY_ROOT } from "@/lib/paths";

export const dynamic = "force-dynamic";

const APPLY_CONFIRMATION = "APPLY_RULE_UNIT_DECISIONS";

export function GET(): Response {
  return Response.json({
    proposal: getRuleUnitApplyProposalSummary(),
  });
}

type ApplyRequestBody = {
  action?: string;
  allowNoop?: boolean;
  confirmation?: string;
};

export async function POST(request: Request): Promise<Response> {
  const body = (await request.json().catch(() => ({}))) as ApplyRequestBody;

  if (body.action === "rebuild") {
    const result = runRuleUnitCommand(["--build-apply-proposal"]);

    if (result instanceof Response) {
      return result;
    }

    return Response.json({
      result,
      proposal: getRuleUnitApplyProposalSummary(),
    });
  }

  if (body.confirmation !== APPLY_CONFIRMATION) {
    return Response.json(
      {
        error: "Confirmation phrase is required before review decisions can be applied.",
        requiredConfirmation: APPLY_CONFIRMATION,
      },
      { status: 400 },
    );
  }

  const args = ["--apply-decisions"];

  if (body.allowNoop === true) {
    args.push("--allow-noop-apply");
  }

  const output = runRuleUnitCommand(args);

  if (output instanceof Response) {
    return output;
  }

  return Response.json({
    result: output,
    proposal: getRuleUnitApplyProposalSummary(),
  });
}

function runRuleUnitCommand(commandArgs: string[]): Response | unknown {
  const pythonCommand = process.env.GEODE_PYTHON ?? "python";
  const args = [
    "-m",
    "geode.pipeline.rule_units",
    "--output-root",
    REPOSITORY_ROOT,
    ...commandArgs,
    "--json",
  ];

  const result = spawnSync(pythonCommand, args, {
    cwd: REPOSITORY_ROOT,
    encoding: "utf8",
  });

  if (result.error) {
    return Response.json(
      {
        error: "Unable to start the apply command.",
        detail: result.error.message,
      },
      { status: 500 },
    );
  }

  if (result.status !== 0) {
    return Response.json(
      {
        error: "Review decisions were not applied.",
        exitCode: result.status,
        stderr: result.stderr.trim(),
        stdout: result.stdout.trim(),
      },
      { status: 400 },
    );
  }

  return JSON.parse(result.stdout);
}
