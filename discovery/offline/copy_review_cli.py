"""
discovery.offline.copy_review_cli — Human Copy Bank Review Tool (P2-7).
§7 implementation-plan.md & §6 architecture.md: Inspects weekly copy bank diffs, approve/reject lines.
"""

from typing import List, Dict, Tuple, Any
from discovery.offline.a3_rulebook_job import A3CellRulebookEntry
from discovery.core.validator import validate_reason_line


class CopyReviewTool:
    """Review tool for weekly copy bank diffs."""

    def __init__(self):
        self.approved_lines: Dict[Tuple[str, int], str] = {}
        self.rejected_lines: Dict[Tuple[str, int], str] = {}

    def review_rulebook_diff(
        self, entries: List[A3CellRulebookEntry], auto_approve_valid: bool = True
    ) -> Dict[str, Any]:
        """
        Reviews new or changed copy lines across rulebook entries.
        Rejections are logged with reasons.
        """
        approved_count = 0
        rejected_count = 0

        for entry in entries:
            for l1_id, line in entry.copy_bank_map.items():
                is_valid, msg = validate_reason_line(line)
                key = (entry.state_id, l1_id)

                if is_valid and auto_approve_valid:
                    self.approved_lines[key] = line
                    approved_count += 1
                else:
                    self.rejected_lines[key] = f"Rejected: {msg}"
                    rejected_count += 1

        return {
            "total_lines_reviewed": len(self.approved_lines) + len(self.rejected_lines),
            "approved_count": approved_count,
            "rejected_count": rejected_count,
            "status": "APPROVED" if rejected_count == 0 else "PARTIAL_REJECTIONS",
        }


def main():
    print("==================================================================")
    print(" THE CART INTERRUPT MVP — PHASE 2 COPY BANK REVIEW TOOL CLI")
    print("==================================================================")
    from discovery.offline.a3_rulebook_job import generate_a3_cell_rulebook

    # Create sample cell rulebook for review demonstration
    sample_entry = generate_a3_cell_rulebook(
        state_id="hh_mgr_01",
        cart_sig="l1:[10]_band:2",
        candidate_l1_ids=[20, 25],
        affinity_reason_map={20: "LIFE_STAGE", 25: "COMPLEMENT"},
        raw_copy_lines={20: "Goes with the wipes you buy", 25: "Best deals guaranteed! Free price discount!"}, # Second fails deny-list
    )

    tool = CopyReviewTool()
    res = tool.review_rulebook_diff([sample_entry], auto_approve_valid=True)

    print(f"Total Lines Reviewed: {res['total_lines_reviewed']}")
    print(f"Approved Copy Lines:  {res['approved_count']}")
    print(f"Rejected Copy Lines:  {res['rejected_count']}")
    print(f"Publication Status:   {res['status']}")
    print("==================================================================")


if __name__ == "__main__":
    from typing import Dict, Any
    main()
