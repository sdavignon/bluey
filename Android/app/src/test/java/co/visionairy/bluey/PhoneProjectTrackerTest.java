package co.visionairy.bluey;

import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Test;
import static org.junit.Assert.*;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class PhoneProjectTrackerTest {
    static class Sheet implements PhoneProjectTracker.Transport {
        LinkedHashMap<String, JSONArray> tabs = new LinkedHashMap<>();
        int writes; boolean fail, badReadback, activityFail;
        Sheet() { for (String tab : PhoneProjectTracker.HEADERS.keySet()) tabs.put(tab, new JSONArray().put(new JSONArray(Arrays.asList(PhoneProjectTracker.HEADERS.get(tab))))); }
        public JSONObject request(String method, String range, JSONArray values) throws Exception {
            if (fail) throw new IllegalStateException("secret-token-not-for-output");
            Matcher m = Pattern.compile("'([^']+)'!A([0-9]+):[A-Z]([0-9]+)").matcher(range);
            assertTrue(m.matches()); String tab = m.group(1); int start = Integer.parseInt(m.group(2)); int end = Integer.parseInt(m.group(3));
            if (method.equals("PUT")) {
                if (activityFail && tab.equals("Activity")) throw new IllegalStateException("failure");
                writes++; tabs.get(tab).put(start - 1, new JSONArray(values.toString())); return new JSONObject();
            }
            if (badReadback && start > 1) return new JSONObject().put("values", new JSONArray().put(new JSONArray().put("wrong")));
            JSONArray result = new JSONArray();
            for (int i = start - 1; i < Math.min(end, tabs.get(tab).length()); i++) result.put(tabs.get(tab).optJSONArray(i) == null ? new JSONArray() : tabs.get(tab).getJSONArray(i));
            return new JSONObject().put("values", result);
        }
    }
    JSONObject run(Sheet s, String tool, JSONObject args) throws Exception { return new JSONObject(PhoneProjectTracker.execute(tool, args.toString(), s)); }
    JSONObject project(Sheet s) throws Exception { return run(s, "upsert_project", new JSONObject().put("record", new JSONObject().put("Project ID", "P1").put("Project", "Bluey").put("Owner", "Scott"))); }
    @Test public void createReadPatchAndRetry() throws Exception {
        Sheet s = new Sheet(); assertEquals("saved", project(s).getString("status"));
        assertEquals("unchanged", project(s).getString("status")); assertEquals(2, s.writes);
        JSONObject record = new JSONObject().put("Project ID", "P1").put("Status", "Active");
        JSONObject saved = run(s, "upsert_project", new JSONObject().put("record", record));
        assertEquals("Scott", saved.getJSONObject("record").getString("Owner"));
        assertEquals(1, run(s, "list_projects", new JSONObject()).getInt("total"));
        assertEquals("Active", run(s, "get_project", new JSONObject().put("id", "P1")).getJSONObject("record").getString("Status"));
    }
    @Test public void duplicateAndHeadersStopWrites() throws Exception {
        Sheet s = new Sheet(); project(s); s.tabs.get("Projects").put(s.tabs.get("Projects").getJSONArray(1));
        assertTrue(project(s).getString("error").contains("duplicate")); assertEquals(2, s.writes);
        Sheet bad = new Sheet(); bad.tabs.get("Notes").getJSONArray(0).put(0, "Wrong");
        assertTrue(project(bad).getString("error").contains("headers")); assertEquals(0, bad.writes);
    }
    @Test public void validatesReferencesAndDate() throws Exception {
        Sheet s = new Sheet();
        JSONObject task = new JSONObject().put("Task ID", "T1").put("Project ID", "P1").put("Task", "Do it");
        assertTrue(run(s, "upsert_task", new JSONObject().put("record", task)).has("error")); project(s);
        assertEquals("saved", run(s, "upsert_task", new JSONObject().put("record", task)).getString("status"));
        task.put("Due date", "2026-02-30"); assertTrue(run(s, "upsert_task", new JSONObject().put("record", task)).has("error"));
    }
    @Test public void notesImmutableAndNoSheetInjection() throws Exception {
        Sheet s = new Sheet(); project(s);
        JSONObject note = new JSONObject().put("Note ID", "N1").put("Project ID", "P1").put("Note", "Hello");
        assertEquals("saved", run(s, "add_project_note", new JSONObject().put("record", note)).getString("status"));
        assertEquals("unchanged", run(s, "add_project_note", new JSONObject().put("record", note)).getString("status"));
        note.put("Note", "changed"); assertTrue(run(s, "add_project_note", new JSONObject().put("record", note)).has("error"));
        assertTrue(run(s, "list_projects", new JSONObject().put("spreadsheet_id", "evil")).has("error"));
    }
    @Test public void transportAndReadbackFailuresSanitized() throws Exception {
        Sheet s = new Sheet(); s.fail = true; String error = project(s).getString("error"); assertFalse(error.contains("secret-token"));
        s.fail = false; s.badReadback = true; assertTrue(project(s).getString("error").contains("readback")); assertEquals(1, s.writes);
    }
    @Test public void activityFailureDoesNotClaimRecordFailed() throws Exception {
        Sheet s = new Sheet(); s.activityFail = true; assertEquals("saved_activity_unverified", project(s).getString("status"));
    }
    @Test public void rawFormulaTextAndBoundedLimit() throws Exception {
        Sheet s = new Sheet(); JSONObject record = new JSONObject().put("Project ID", "P1").put("Project", "=IMPORTXML(whatever)");
        assertEquals("=IMPORTXML(whatever)", run(s, "upsert_project", new JSONObject().put("record", record)).getJSONObject("record").getString("Project"));
        assertTrue(run(s, "list_projects", new JSONObject().put("limit", 5001)).has("error"));
        s.tabs.get("Projects").put(5001, new JSONArray().put("overflow").put("test"));
        assertTrue(run(s, "list_projects", new JSONObject()).getString("error").contains("5000"));
    }
    @Test public void validatesWorkbookUrlAndSchemaCount() throws Exception {
        assertEquals(7, PhoneProjectTracker.TOOL_SCHEMAS.length());
        assertEquals("abc123", PhoneProjectTracker.spreadsheetId("https://docs.google.com/spreadsheets/d/abc123/edit#gid=0"));
        assertTrue(new JSONObject(PhoneProjectTracker.dispatch("list_projects", "{}", "token", "https://evil.example/sheet")).has("error"));
    }
}
