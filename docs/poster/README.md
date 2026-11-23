# Group 30 poster source and review materials

Both poster layouts can be rebuilt from this checkout. The ASU version uses
a maroon and gold capstone layout with a screenshot. The editorial version
uses a dark header, a worked example, and a recall chart. Both present the
full product workflow and report the measured Milestone 2 results.

| Material | Where to find it |
| --- | --- |
| Poster builder and editorial layout | [build_poster.py](build_poster.py) |
| ASU layout | [asu_layout.py](asu_layout.py) |
| All six screenshots and captions sent for stakeholder review | [screenshots](screenshots/README.md) |
| Project overview shared with Neha | [Stakeholder review artifact](https://claude.ai/artifact/PbPucZ6MH3Kn4XrK9ECu6U#s1) |
| Final submitted report and stakeholder feedback | [Milestone 2 deployment report](Milestone2_Deployment_Report.pdf) |
| Evaluation figures | [Frozen copy of the Milestone 2 results CSV](milestone2_results.csv) |
| Remaining implementation and December 2 rehearsal | [Final demo handoff](../final_demo_handoff.md) |

## Rebuild either poster

From the repository root with your Python environment activated:

```bash
python -m pip install reportlab
python docs/poster/build_poster.py asu --output output/pdf/Group30_Poster_ASU.pdf
python docs/poster/build_poster.py editorial --output output/pdf/Group30_Poster_Editorial.pdf
```

Edit the layout files to change copy or swap screenshots. The ASU version
uses the action review image from the offline walkthrough. Refresh the
image dimensions in the layout if the replacement has a different aspect
ratio. Rebuild and check the rendered page before handing off. Keep the
final export at 24 × 36 inches in portrait and use `Group30_Poster.pdf`
as the upload filename.

The builders use a frozen copy of the results CSV from commit `e54e61a`.
If you replace it with a new evaluation, update the chart, written totals,
and evaluation citation together.
