// Link ids and total labels for matrix cells (PLAN §3.4.2, §3.6).
//
// A matrix cell (row R receives, column C pays) is the node pair whose link id is "C--R". Its
// positive part is "C--R", its negative part "C--R~neg" and the whole pair "C--R~pair". The cell
// shows the net value, so its total label is the pinned label of the part(s) it contains.

import { linkId } from "../ids";
import type { MatrixPinned } from "./types";

export { linkId };

export interface TotalInfo {
  total: "official" | "derived" | null;
  pins: string[];
  /** Which pinned key matched ("pair" when the net of both parts is held to a published figure). */
  part: "pos" | "neg" | "pair" | null;
}

export function totalFor(
  pinned: MatrixPinned,
  payer: string,
  receiver: string,
  pos: number,
  neg: number,
): TotalInfo {
  const id = linkId(payer, receiver);
  const hasPos = pos > 0;
  const hasNeg = neg < 0;
  const pick = (key: string, part: TotalInfo["part"]): TotalInfo | null => {
    const p = pinned[key];
    return p ? { total: p.total, pins: p.pins, part } : null;
  };
  let hit: TotalInfo | null = null;
  const pair = linkId(payer, receiver, "pair");
  if (hasPos && hasNeg) hit = pick(pair, "pair");
  else if (hasPos) hit = pick(id, "pos") ?? pick(pair, "pair");
  else if (hasNeg) hit = pick(linkId(payer, receiver, "neg"), "neg") ?? pick(pair, "pair");
  return hit ?? { total: null, pins: [], part: null };
}
