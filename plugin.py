from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from maibot_sdk import Field, MaiBotPlugin, PluginConfigBase, Tool
from maibot_sdk.types import ToolParameterInfo, ToolParamType


class PluginSectionConfig(PluginConfigBase):
    __ui_label__ = "插件"
    __ui_icon__ = "package"
    __ui_order__ = 0
    enabled: bool = Field(default=False, description="是否启用插件")
    config_version: str = Field(default="0.1.0", description="配置版本号")


class KnowledgeBaseConfig(PluginConfigBase):
    __ui_label__ = "知识库"
    __ui_icon__ = "file-text"
    __ui_order__ = 1
    folder_path: str = Field(default="knowledge_base", description="知识库文件夹路径（相对于插件目录）")
    file_name: str = Field(default="data.txt", description="要读取的文件名")
    model: str = Field(default="planner", description="使用的 LM 模型（planner/replyer/utils）")
    detail_prompt: str = Field(
        default="请以详细的方式描述",
        description="复杂程度提示词（直接传给 LLM）"
    )
    cache_folder: str = Field(default="cache", description="缓存文件夹路径（相对于插件目录）")
    enable_cache: bool = Field(default=True, description="是否启用缓存")
    llm_timeout_seconds: int = Field(default=30, description="LM 超时时间（秒）")


class CustomAPIConfig(PluginConfigBase):
    __ui_label__ = "自定义 API"
    __ui_icon__ = "cloud"
    __ui_order__ = 2
    enabled: bool = Field(default=False, description="是否使用自定义 API")
    api_url: str = Field(default="", description="自定义 API 地址")
    api_key: str = Field(default="", description="自定义 API 密钥")
    model: str = Field(default="", description="自定义模型名称")


class MyPluginConfig(PluginConfigBase):
    plugin: PluginSectionConfig = Field(default_factory=PluginSectionConfig)
    knowledge_base: KnowledgeBaseConfig = Field(default_factory=KnowledgeBaseConfig)
    custom_api: CustomAPIConfig = Field(default_factory=CustomAPIConfig)


class MyPlugin(MaiBotPlugin):
    config_model = MyPluginConfig

    async def on_load(self) -> None:
        self._plugin_dir = Path(__file__).parent
        self._write_lock = asyncio.Lock()          # 新增：写锁
        self._ensure_folders()

    async def on_unload(self) -> None:
        pass

    async def on_config_update(self, scope: str, config_data: dict, version: str) -> None:
        del scope, config_data, version
        self._ensure_folders()

    def _ensure_folders(self) -> None:
        kb_folder = self._plugin_dir / self.config.knowledge_base.folder_path
        cache_folder = self._plugin_dir / self.config.knowledge_base.cache_folder
        kb_folder.mkdir(parents=True, exist_ok=True)
        cache_folder.mkdir(parents=True, exist_ok=True)

    def _get_knowledge_file_path(self) -> Path:
        return self._plugin_dir / self.config.knowledge_base.folder_path / self.config.knowledge_base.file_name

    def _get_cache_folder_path(self) -> Path:
        return self._plugin_dir / self.config.knowledge_base.cache_folder

    def _sanitize_filename(self, keyword: str) -> str:
        import re
        sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', keyword)
        return sanitized[:100]

    def _list_cache_files(self) -> list[str]:
        cache_folder = self._get_cache_folder_path()
        cache_files = []
        for file in cache_folder.glob("*.json"):
            cache_files.append(file.stem)
        return cache_files

    def _read_cache(self, keyword: str) -> str | None:
        cache_file = self._get_cache_folder_path() / f"{self._sanitize_filename(keyword)}.json"
        if not cache_file.exists():
            return None
        try:
            with cache_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("content", "")
        except Exception as e:
            self.ctx.logger.warning(f"读取缓存失败: {e}")
            return None

    async def _write_cache(self, keyword: str, content: str) -> None:
        """异步写入缓存（受锁保护）"""
        cache_file = self._get_cache_folder_path() / f"{self._sanitize_filename(keyword)}.json"
        async with self._write_lock:
            try:
                with cache_file.open("w", encoding="utf-8") as f:
                    json.dump({"keyword": keyword, "content": content}, f, ensure_ascii=False, indent=2)
            except Exception as e:
                self.ctx.logger.error(f"写入缓存失败: {e}", exc_info=True)

    async def _call_llm(self, prompt: str) -> dict[str, Any]:
        timeout = self.config.knowledge_base.llm_timeout_seconds

        if self.config.custom_api.enabled:
            if not self.config.custom_api.api_url or not self.config.custom_api.model:
                return {"success": False, "response": "", "error": "自定义 API 配置不完整"}

            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    headers = {}
                    if self.config.custom_api.api_key:
                        headers["Authorization"] = f"Bearer {self.config.custom_api.api_key}"

                    payload = {
                        "model": self.config.custom_api.model,
                        "messages": [{"role": "user", "content": prompt}]
                    }

                    async with session.post(
                        self.config.custom_api.api_url,
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=timeout)
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                            return {"success": True, "response": content}
                        else:
                            error_text = await resp.text()
                            return {"success": False, "response": "", "error": f"API 返回错误: {error_text}"}
            except Exception as e:
                self.ctx.logger.error(f"自定义 API 调用失败: {e}", exc_info=True)
                return {"success": False, "response": "", "error": str(e)}

        try:
            result = await asyncio.wait_for(
                self.ctx.llm.generate(prompt, self.config.knowledge_base.model),
                timeout=timeout
            )
            return result
        except asyncio.TimeoutError:
            return {"success": False, "response": "", "error": "LLM 调用超时"}
        except Exception as e:
            self.ctx.logger.error(f"LLM 调用失败: {e}", exc_info=True)
            return {"success": False, "response": "", "error": str(e)}

    async def _should_use_cache(self, keyword: str, cache_files: list[str]) -> tuple[bool, str]:
        if not cache_files:
            return False, ""

        prompt = (
            f"用户查询关键词: 「{keyword}」\n"
            f"现有缓存列表: {', '.join(cache_files)}\n\n"
            "请判断是否可以直接使用现有缓存中的某一个来回答用户查询。\n"
            "如果可以使用，请只返回缓存名称（不含扩展名）。\n"
            "如果不可以使用任何缓存，请只返回「无」。"
        )

        result = await self._call_llm(prompt)
        if not result.get("success"):
            return False, ""

        response = result.get("response", "").strip()
        if response == "无" or not response:
            return False, ""

        if response in cache_files:
            return True, response

        return False, ""

    async def _query_llm(self, keyword: str, content: str) -> str:
        detail_prompt = self.config.knowledge_base.detail_prompt
        prompt = (
            f"请从以下内容中提取与「{keyword}」相关的信息，并{detail_prompt}：\n\n"
            f"== 内容开始 ===\n"
            f"{content}\n"
            f"=== 内容结束 ===\n"
            f"请直接输出提取的内容，不要添加额外说明。"
        )

        result = await self._call_llm(prompt)
        if result.get("success"):
            return result.get("response", "")
        return ""

    @Tool(
        "knowledge_query",
        description="从知识库文件中查询与关键词相关的内容，基于 LLM 智能提取",
        parameters=[
            ToolParameterInfo(
                name="keyword",
                param_type=ToolParamType.STRING,
                description="查询的关键词或关键句",
                required=True
            ),
        ],
    )
    async def handle_knowledge_query(self, keyword: str = "", stream_id: str = "", **kwargs: Any) -> dict[str, str]:
        del stream_id, kwargs

        if not keyword:
            return {"name": "knowledge_query", "content": "", "error": "关键词不能为空"}

        kb_file = self._get_knowledge_file_path()
        if not kb_file.exists():
            return {
                "name": "knowledge_query",
                "content": "",
                "error": f"知识库文件不存在: {self.config.knowledge_base.file_name}"
            }

        try:
            with kb_file.open("r", encoding="utf-8") as f:
                file_content = f.read()
        except Exception as e:
            self.ctx.logger.error(f"读取知识库文件失败: {e}", exc_info=True)
            return {
                "name": "knowledge_query",
                "content": "",
                "error": f"读取文件失败: {e}"
            }

        if not file_content.strip():
            return {"name": "knowledge_query", "content": "", "error": "知识库文件为空"}

        if self.config.knowledge_base.enable_cache:
            cache_files = self._list_cache_files()
            if cache_files:
                use_cache, cache_name = await self._should_use_cache(keyword, cache_files)
                if use_cache:
                    cached_content = self._read_cache(cache_name)
                    if cached_content:
                        self.ctx.logger.info(f"使用缓存: {cache_name}")
                        return {"name": "knowledge_query", "content": cached_content}

        extracted_content = await self._query_llm(keyword, file_content)

        if not extracted_content:
            self.ctx.logger.warning("LM 调用失败，返回原文件内容")
            return {
                "name": "knowledge_query",
                "content": file_content,
                "error": "LLM 调用失败，已返回原文件内容"
            }

        if self.config.knowledge_base.enable_cache:
            await self._write_cache(keyword, extracted_content)   # 改为 await

        return {"name": "knowledge_query", "content": extracted_content}


def create_plugin() -> MyPlugin:
    return MyPlugin()