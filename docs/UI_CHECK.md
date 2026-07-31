# Interface Check

The interface check instantiates every workspace with an offscreen Qt platform at three common screen
sizes. It verifies scrollable workspace wrappers, readable button heights, adaptive navigation, and page
availability. Optional screenshots are written to the local `ui-check` folder.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\ui_check.ps1
```
