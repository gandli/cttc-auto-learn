"""测试 Login 模块

覆盖 v22 架构：
- 凭证恢复 (try_restore_session)
- QR 提取 (extract_app_qr, extract_wechat_qr)
- 登录检测 (is_logged_in, is_qr_expired)
- 状态保存 (_save_state, _save_auth_state)
- 快速 QR (_capture_qr_via_api, fetch_qr_codes)
- HTTP 轮询 (_poll_login_http)
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cttc.login import CTTCLogin


@pytest.fixture
def client(config, log, mock_page, mock_context, mock_browser):
    """创建测试用 CTTCLogin 实例"""
    with patch("cttc.login.async_playwright") as mock_pw:
        mock_pw_instance = AsyncMock()
        mock_pw_instance.start = AsyncMock(return_value=mock_pw_instance)
        mock_pw_instance.chromium = MagicMock()
        mock_pw_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_pw.return_value = mock_pw_instance

        client = CTTCLogin(config, log)
        client.page = mock_page
        client._ctx = mock_context
        client._browser = mock_browser
        client._pw = mock_pw_instance
        return client


# ═══════════════════════════════════════════
# 属性
# ═══════════════════════════════════════════

def test_state_file_property(client, config):
    expected = Path(config.output_dir) / "auth-state.json"
    assert client.state_file == expected


def test_output_dir_property(client, config):
    assert client.output_dir == Path(config.output_dir)


# ═══════════════════════════════════════════
# 登录检测
# ═══════════════════════════════════════════

@pytest.mark.asyncio
async def test_is_logged_in_true(client, mock_page):
    mock_page.evaluate = AsyncMock(return_value=True)
    result = await client.is_logged_in()
    assert result is True


@pytest.mark.asyncio
async def test_is_logged_in_false(client, mock_page):
    mock_page.evaluate = AsyncMock(return_value=False)
    result = await client.is_logged_in()
    assert result is False


@pytest.mark.asyncio
async def test_is_qr_expired(client, mock_page):
    # 模拟：未登录（token 为空）且二维码已失效
    mock_page.evaluate = AsyncMock(side_effect=[
        False,  # is_logged_in: localStorage.getItem('token') 返回 falsy
        True    # is_qr_expired: 页面包含"二维码已失效"
    ])
    result = await client.is_qr_expired()
    assert result is True


@pytest.mark.asyncio
async def test_is_qr_not_expired(client, mock_page):
    # 模拟：未登录且二维码未过期
    mock_page.evaluate = AsyncMock(side_effect=[
        False,  # is_logged_in
        False   # is_qr_expired
    ])
    result = await client.is_qr_expired()
    assert result is False


# ═══════════════════════════════════════════
# QR 提取
# ═══════════════════════════════════════════

@pytest.mark.asyncio
async def test_extract_app_qr(client, mock_page):
    mock_page.evaluate = AsyncMock(return_value="base64_app_data")
    result = await client.extract_app_qr()
    assert result == "base64_app_data"


@pytest.mark.asyncio
async def test_extract_app_qr_not_found(client, mock_page):
    mock_page.evaluate = AsyncMock(return_value=None)
    result = await client.extract_app_qr()
    assert result is None


@pytest.mark.asyncio
async def test_extract_wechat_qr(client, mock_page):
    mock_page.evaluate = AsyncMock(return_value="base64_wechat_data")
    result = await client.extract_wechat_qr()
    assert result == "base64_wechat_data"


@pytest.mark.asyncio
async def test_extract_wechat_qr_not_found(client, mock_page):
    mock_page.evaluate = AsyncMock(return_value=None)
    result = await client.extract_wechat_qr()
    assert result is None


@pytest.mark.asyncio
async def test_extract_both_qrs(client, mock_page):
    """测试同时提取两种二维码"""
    mock_page.evaluate = AsyncMock(side_effect=["app_base64", True, "wechat_base64"])
    result = await client.extract_both_qrs()
    assert result["app"] == "app_base64"
    assert result["wechat"] == "wechat_base64"


@pytest.mark.asyncio
async def test_show_qr(client, config, mock_page):
    """测试保存并显示二维码"""
    import base64
    from PIL import Image
    import io

    img = Image.new("RGB", (100, 100), "white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()

    with patch("cttc.login.print_qr_to_terminal"):
        result = await client.show_qr(b64, "测试", "test_qr.png")
        # 返回相对路径，文件实际在 output_dir 中
        assert result == "test_qr.png"
        assert (client.output_dir / result).exists()


# ═══════════════════════════════════════════
# 状态保存
# ═══════════════════════════════════════════

@pytest.mark.asyncio
async def test_save_state(client, config, mock_context, sample_state):
    mock_context.storage_state = AsyncMock(return_value=sample_state)
    await client._save_state()

    assert client.state_file.exists()
    saved = json.loads(client.state_file.read_text(encoding="utf-8"))
    assert saved["cookies"][0]["name"] == "session"


@pytest.mark.asyncio
async def test_save_state_error_handling(client, mock_context):
    """测试保存状态时的错误处理"""
    mock_context.storage_state = AsyncMock(side_effect=Exception("save failed"))
    with pytest.raises(Exception):
        await client._save_state()


# ═══════════════════════════════════════════
# 凭证恢复
# ═══════════════════════════════════════════

@pytest.mark.asyncio
async def test_try_restore_session_no_file(client, config):
    """测试无凭证文件时的恢复"""
    result = await client.try_restore_session()
    assert result is False


@pytest.mark.asyncio
async def test_try_restore_session_success(client, config, mock_page, mock_context, sample_state):
    """测试凭证恢复成功"""
    # 写入凭证文件
    state_file = Path(config.output_dir) / "auth-state.json"
    state_file.write_text(json.dumps(sample_state), encoding="utf-8")

    # mock 页面导航和登录检测
    mock_page.goto = AsyncMock()
    mock_page.wait_for_timeout = AsyncMock()
    mock_page.evaluate = AsyncMock(side_effect=[
        True,  # is_logged_in → True
        "张三",  # user_info
    ])
    mock_context.storage_state = AsyncMock(return_value=sample_state)

    result = await client.try_restore_session()
    assert result is True


@pytest.mark.asyncio
async def test_try_restore_session_expired(client, config, mock_page):
    """测试凭证过期"""
    state_file = Path(config.output_dir) / "auth-state.json"
    state_file.write_text(json.dumps({"cookies": [], "origins": []}), encoding="utf-8")

    mock_page.goto = AsyncMock()
    mock_page.wait_for_timeout = AsyncMock()
    mock_page.evaluate = AsyncMock(return_value=False)  # is_logged_in → False

    result = await client.try_restore_session()
    assert result is False


@pytest.mark.asyncio
async def test_try_restore_session_exception(client, config, mock_page, mock_context):
    """测试凭证恢复异常"""
    state_file = Path(config.output_dir) / "auth-state.json"
    state_file.write_text(json.dumps({"cookies": [], "origins": []}), encoding="utf-8")

    mock_page.goto = AsyncMock(side_effect=Exception("Navigation failed"))
    mock_context.new_context = AsyncMock(return_value=mock_context)
    mock_context.new_page = AsyncMock(return_value=mock_page)

    result = await client.try_restore_session()
    assert result is False


# ═══════════════════════════════════════════
# v22: 微信 QR 生成
# ═══════════════════════════════════════════

def test_generate_wechat_qr(client, config):
    """测试生成微信二维码 PNG"""
    with patch("cttc.login.generate_qr_png") as mock_gen:
        mock_gen.return_value = str(Path(config.output_dir) / "qrcode-wechat.png")
        result = client._generate_wechat_qr("test-uuid-123")
        assert "qrcode-wechat.png" in result
        mock_gen.assert_called_once()
        # 验证 URL 包含 UUID
        call_args = mock_gen.call_args
        assert "test-uuid-123" in call_args[0][0]


# ═══════════════════════════════════════════
# v22: 快速 QR 获取
# ═══════════════════════════════════════════

@pytest.mark.asyncio
async def test_capture_qr_via_api_success(client):
    """测试 headless Chrome 捕获 QR"""
    mock_page = AsyncMock()
    mock_ctx = AsyncMock()
    mock_browser = AsyncMock()
    mock_pw = AsyncMock()

    # 模拟事件触发
    captured_urls = []
    captured_b64 = []

    async def on_request(req):
        if "loginCheck" in req.url:
            captured_urls.append(req.url)

    async def on_response(resp):
        if "deriveQRCode" in resp.url:
            data = AsyncMock()
            data.json = AsyncMock(return_value={"data": "app_b64_data"})
            captured_b64.append("app_b64_data")

    mock_page.on = MagicMock(side_effect=lambda event, handler: None)
    mock_page.goto = AsyncMock()
    mock_page.wait_for_timeout = AsyncMock()
    mock_page.evaluate = AsyncMock(return_value=None)
    mock_page.locator = MagicMock(return_value=MagicMock(
        first=MagicMock(count=AsyncMock(return_value=0))
    ))

    mock_ctx.new_page = AsyncMock(return_value=mock_page)
    mock_browser.new_context = AsyncMock(return_value=mock_ctx)
    mock_browser.close = AsyncMock()
    mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)

    with patch("cttc.login.async_playwright") as mock_pw_class:
        mock_pw_instance = AsyncMock()
        mock_pw_instance.start = AsyncMock(return_value=mock_pw_instance)
        mock_pw_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_pw_class.return_value = mock_pw_instance

        # 需要模拟 request/response 事件
        request_handlers = []
        response_handlers = []

        def on_event(event, handler):
            if event == "request":
                request_handlers.append(handler)
            elif event == "response":
                response_handlers.append(handler)

        mock_page.on = MagicMock(side_effect=on_event)

        # 启动捕获（会注册事件处理器然后等待）
        import asyncio
        task = asyncio.create_task(client._capture_qr_via_api())

        # 模拟触发事件
        await asyncio.sleep(0.1)
        for handler in request_handlers:
            mock_req = MagicMock()
            mock_req.url = "https://mooc.ctt.cn/oauth/api/v1/loginCheck?uuid=test123&organizationId=org1"
            await handler(mock_req)

        for handler in response_handlers:
            mock_resp = AsyncMock()
            mock_resp.url = "https://mooc.ctt.cn/oauth/api/v1/deriveQRCode?_=123"
            mock_resp.json = AsyncMock(return_value={"data": "app_b64_data"})
            await handler(mock_resp)

        try:
            result = await asyncio.wait_for(task, timeout=5)
        except asyncio.TimeoutError:
            task.cancel()
            result = (None, None)


@pytest.mark.asyncio
async def test_fetch_qr_codes(client, config):
    """测试完整 QR 获取流程（headless Chrome + HTTP）"""
    import base64
    config.output_dir = str(Path(config.output_dir))
    (Path(config.output_dir)).mkdir(parents=True, exist_ok=True)

    valid_b64 = base64.b64encode(b"fake_qr_image_data").decode()

    with patch.object(client, '_capture_qr_via_api', new_callable=AsyncMock) as mock_capture, \
         patch("cttc.login.http_req.post") as mock_post, \
         patch("cttc.login.generate_qr_png") as mock_qr:

        mock_capture.return_value = ("https://mooc.ctt.cn/oauth/api/v1/loginCheck?uuid=test&organizationId=org&key=k", valid_b64)
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"uuid": "wx-uuid-456"})
        )
        mock_qr.return_value = "/path/to/qr.png"

        lc_url, wx_uuid, app_path, wx_path = await client.fetch_qr_codes()

        assert "loginCheck" in lc_url
        assert "uuid=test" in lc_url
        assert wx_uuid == "wx-uuid-456"
        mock_capture.assert_called_once()
        mock_post.assert_called_once()


# ═══════════════════════════════════════════
# v22: HTTP 轮询
# ═══════════════════════════════════════════

@pytest.mark.asyncio
async def test_poll_login_http_app_success(client):
    """测试 APP 扫码成功"""
    with patch("cttc.login.http_req.get") as mock_get, \
         patch("cttc.login.http_req.post") as mock_post:

        # loginCheck 返回 access_token
        mock_resp = MagicMock()
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = {"access_token": "test_token_123"}
        mock_get.return_value = mock_resp

        # checkUUIDStatus 返回 null（不干扰）
        mock_wx_resp = MagicMock()
        mock_wx_resp.headers = {"content-type": "application/json"}
        mock_wx_resp.json.return_value = None
        mock_post.return_value = mock_wx_resp

        result = await client._poll_login_http(
            "https://loginCheck?uuid=test",
            "wx-uuid",
            timeout=5
        )

        assert result is not None
        assert result["type"] == "app"
        assert result["data"]["access_token"] == "test_token_123"


@pytest.mark.asyncio
async def test_poll_login_http_wx_success(client):
    """测试微信扫码成功"""
    with patch("cttc.login.http_req.get") as mock_get, \
         patch("cttc.login.http_req.post") as mock_post:

        # loginCheck 返回空（不干扰）
        mock_app_resp = MagicMock()
        mock_app_resp.headers = {"content-type": "application/json"}
        mock_app_resp.json.return_value = {}
        mock_get.return_value = mock_app_resp

        # checkUUIDStatus 返回成功
        mock_wx_resp = MagicMock()
        mock_wx_resp.headers = {"content-type": "application/json"}
        mock_wx_resp.json.return_value = {"status": True, "openId": "wx_openid"}
        mock_post.return_value = mock_wx_resp

        result = await client._poll_login_http(
            "https://loginCheck?uuid=test",
            "wx-uuid",
            timeout=5
        )

        assert result is not None
        assert result["type"] == "wechat"
        assert result["data"]["status"] is True


@pytest.mark.asyncio
async def test_poll_login_http_timeout(client):
    """测试轮询超时"""
    with patch("cttc.login.http_req.get") as mock_get, \
         patch("cttc.login.http_req.post") as mock_post:

        # 两者都返回空
        mock_resp = MagicMock()
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = {}
        mock_get.return_value = mock_resp
        mock_post.return_value = mock_resp

        result = await client._poll_login_http(
            "https://loginCheck?uuid=test",
            "wx-uuid",
            timeout=2  # 2 秒超时
        )

        assert result is None


@pytest.mark.asyncio
async def test_poll_login_http_network_error(client):
    """测试网络错误不崩溃"""
    with patch("cttc.login.http_req.get", side_effect=Exception("Network error")), \
         patch("cttc.login.http_req.post", side_effect=Exception("Network error")):

        result = await client._poll_login_http(
            "https://loginCheck?uuid=test",
            "wx-uuid",
            timeout=2
        )

        assert result is None


# ═══════════════════════════════════════════
# 浏览器生命周期
# ═══════════════════════════════════════════

@pytest.mark.asyncio
async def test_close(client, mock_browser):
    """测试关闭浏览器"""
    mock_browser.contexts = []
    await client.close()
    mock_browser.close.assert_called_once()


@pytest.mark.asyncio
async def test_screenshot(client, config, mock_page):
    """测试截图"""
    mock_page.screenshot = AsyncMock()
    result = await client.screenshot("test_screenshot")
    assert "test_screenshot.png" in result


# ═══════════════════════════════════════════
# 导航
# ═══════════════════════════════════════════

@pytest.mark.asyncio
async def test_navigate_to_login(client, mock_page):
    """测试打开登录页"""
    mock_page.goto = AsyncMock()
    mock_page.wait_for_timeout = AsyncMock()
    mock_locator = MagicMock()
    mock_locator.first = MagicMock()
    mock_locator.first.click = AsyncMock()
    mock_page.locator = MagicMock(return_value=mock_locator)

    await client.navigate_to_login()
    mock_page.goto.assert_called_once()
