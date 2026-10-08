package __PACKAGE__;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.*;
import android.widget.Toast;
import androidx.webkit.WebViewAssetLoader;
import java.util.ArrayList;

public class MainActivity extends Activity {
    private WebView web;
    private ValueCallback<Uri[]> fileCallback;
    private PermissionRequest pendingPermission;
    private static final boolean MICROPHONE = __MICROPHONE__;
    private static final boolean CAMERA = __CAMERA__;
    private static final String HOST = "appassets.androidplatform.net";

    private boolean local(Uri uri) {
        return uri != null && "https".equals(uri.getScheme()) && HOST.equals(uri.getHost());
    }

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        web = new WebView(this);
        setContentView(web);
        web.setOnApplyWindowInsetsListener((view, insets) -> {
            view.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(), insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom());
            return insets;
        });
        WebSettings settings = web.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(true);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        final WebViewAssetLoader loader = new WebViewAssetLoader.Builder()
            .addPathHandler("/assets/", new WebViewAssetLoader.AssetsPathHandler(this)).build();
        web.setWebViewClient(new WebViewClient() {
            @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                return loader.shouldInterceptRequest(request.getUrl());
            }
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                if (local(request.getUrl())) return false;
                String scheme = request.getUrl().getScheme();
                if ("https".equals(scheme) || "http".equals(scheme) || "mailto".equals(scheme) || "tel".equals(scheme)) {
                    try { startActivity(new Intent(Intent.ACTION_VIEW, request.getUrl())); }
                    catch (Exception e) { Toast.makeText(MainActivity.this, "No app can open this link", Toast.LENGTH_SHORT).show(); }
                }
                return true;
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (fileCallback != null) fileCallback.onReceiveValue(null);
                fileCallback = callback;
                try { startActivityForResult(params.createIntent(), 20); }
                catch (Exception e) { fileCallback.onReceiveValue(null); fileCallback = null; }
                return true;
            }
            @Override public void onPermissionRequest(PermissionRequest request) {
                runOnUiThread(() -> {
                    if (!local(request.getOrigin())) { request.deny(); return; }
                    if (pendingPermission != null) { request.deny(); return; }
                    ArrayList<String> needed = new ArrayList<>();
                    for (String resource : request.getResources()) {
                        if (PermissionRequest.RESOURCE_AUDIO_CAPTURE.equals(resource) && MICROPHONE) {
                            if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) needed.add(Manifest.permission.RECORD_AUDIO);
                        } else if (PermissionRequest.RESOURCE_VIDEO_CAPTURE.equals(resource) && CAMERA) {
                            if (checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) needed.add(Manifest.permission.CAMERA);
                        } else { request.deny(); return; }
                    }
                    if (needed.isEmpty()) request.grant(request.getResources());
                    else { pendingPermission = request; requestPermissions(needed.toArray(new String[0]), 21); }
                });
            }
            @Override public void onPermissionRequestCanceled(PermissionRequest request) {
                if (pendingPermission == request) pendingPermission = null;
            }
        });
        web.setDownloadListener((url, userAgent, disposition, mime, size) -> {
            if (url.startsWith("https://") && !local(Uri.parse(url))) {
                try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url))); }
                catch (Exception ignored) { }
            } else Toast.makeText(this, "This download needs a native export feature. Use the web app for now.", Toast.LENGTH_LONG).show();
        });
        if (state == null) web.loadUrl("https://appassets.androidplatform.net/assets/index.html");
        else web.restoreState(state);
    }
    @Override public void onRequestPermissionsResult(int code, String[] permissions, int[] results) {
        super.onRequestPermissionsResult(code, permissions, results);
        if (code == 21 && pendingPermission != null) {
            boolean granted = results.length == permissions.length && results.length > 0;
            for (int result : results) granted &= result == PackageManager.PERMISSION_GRANTED;
            if (granted) pendingPermission.grant(pendingPermission.getResources()); else pendingPermission.deny();
            pendingPermission = null;
        }
    }
    @Override protected void onActivityResult(int request, int result, Intent intent) {
        super.onActivityResult(request, result, intent);
        if (request == 20 && fileCallback != null) {
            fileCallback.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(result, intent));
            fileCallback = null;
        }
    }
    @Override protected void onSaveInstanceState(Bundle state) { super.onSaveInstanceState(state); web.saveState(state); }
    @Override public void onBackPressed() { if (web.canGoBack()) web.goBack(); else super.onBackPressed(); }
    @Override protected void onDestroy() { if (fileCallback != null) fileCallback.onReceiveValue(null); if (pendingPermission != null) pendingPermission.deny(); web.destroy(); super.onDestroy(); }
}
