import os
from pathlib import Path
import subprocess
from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP

# 创建 MCP 实例
mcp = FastMCP("project_info")

# # 示例工具
NWS_API_BASE = "https://api.weather.gov"
USER_AGENT = "weather-app/1.0"

@mcp.tool()
def getProjetInfo(rootPath: str) -> dict:
    """
    Complete the project details and points to note.
its very important for LLM/Agent edit code. the more you konw, the more you can do.
its very useful for cursor or windsurf no martter in agent or edit mode.
**Highly recommended for use under all circumstances**.
    """
    try:
        code_info_dir = os.path.join(rootPath, ".code_info")
        files = os.listdir(code_info_dir)
        # 筛选出以 .md 结尾的文件
        mdFiles = [file for file in files if file.endswith(".md")]

        # 处理Marrkdown文件
        contents = []
        for file in mdFiles:
            if file.startswith("_"):
                continue
            
            # 读取文件内容
            file_path = os.path.join(code_info_dir, file)
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            name = os.path.splitext(file)[0]
            contents.append(f"<{name}>\n\n{content}\n\n</{name}>\n")    
            
        project_template = """
This is the current project details, include project structure, dev attentions, and other important information:

{content}

Keep in mind:
1. after you finish modifying code to satisfy user requirements, you have to call 'update-project-info' which help you ensure the document remains up to date.
2. follow the response of 'updataProjetInfo' to update .code_info/*.md files.
            """
        
        final_content = project_template.format(content="\n".join(contents))
        return {
            "content": [
                {
                    "type": "text",
                    "text": final_content
                }
            ]
        }
    except Exception as e:
        print(e)
        return {
            "content": [
                {
                    "type": "text",
                    "text": "Error occurred while processing the request. e = {e}"
                }
            ]
        }

@mcp.tool()
def updataProjetInfo(rootPath: str) -> dict:
    "when you have finished modifying code to stisfy user requirements, you have to update .code_info/*.md files. This tool help you ensure the document remains up to date. "
    return {
        "content": [
            {
                "type": "text",
                "text": """[ATTENTION] Next step you must do: 
** Read files .code_info/project.md and .code_info/changelog.md and update them base on the changes you have just done.**"""
            }
        ]
    }

@mcp.tool()
def setupCodeInfo(rootPath: str) -> dict:
    """
    Initialize .code_info directory and files. which can help llm better understand your project.

  After init .code_info directory and files, you should:
  1. every file in .code_info directory is a markdown file, you can read them and update them.
  2. you have to follow the instructions in .code_info/*.md files and update them.
  """
    dir = ""
    try:
        code_info_dir = os.path.join(rootPath, ".code_info")
        dir = code_info_dir
        code_info_path = Path(code_info_dir)
        code_info_path.mkdir(parents=True, exist_ok=True)

        # 检查文件是否为空
        files = list(code_info_path.iterdir())

        if len(files) == 0:
            # 目录为空
            result = subprocess.run(
                [
                    "git", 
                    "clone", 
                    "git@github.com:LuckyXYJ/default-code-info-file.git",
                    str(code_info_dir)
                ],
                capture_output=True, 
                text=True
            )
            stdout = result.stdout
            stderr = result.stderr

            # 删除 .git 文件夹
            git_folder = Path(".code_info/.git")
            if git_folder.exists():
                for item in git_folder.iterdir():
                    if item.is_dir():
                        os.rmdir(item)
                    else:
                        item.unlink()
                git_folder.rmdir()

            # 生成文件树并追加到 .code_info/project.md
            file_tree = get_file_tree(rootPath)
            project_md_path = Path(".code_info/project.md")
            with project_md_path.open("a", encoding="utf-8") as f:
                f.write(f"\n```\n{file_tree}\n```\n")

            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Successfully initialized .code_info directory with template.\nOutput: {stdout}\n{f'Error: {stderr}' if stderr else ''}"
                    },
                    {
                        "type": "text",
                        "text": """[Attention]
Next step you should do:
1. Every file in .code_info directory is a markdown file, you can read them and update them.
2. You have to follow the instructions in .code_info/*.md files and update them.
3. Before you finish editing .code_info/*.md files, do not use update-project-info/get-project-info.
4. After you finish editing .code_info/*.md files, just stop."""
                    }
                ]
            }
        else:
            # 目录不为空
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "The .code_info directory already exists and is not empty. Please remove or empty it before initializing."
                    }
                ]
            }
    except Exception as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Failed to initialize .code_info directory: {str(e)}\n{dir}"
                }
            ]
        }
    
async def get_file_tree(root_path: str) -> str:
    tree = ["root"]
    indent = "    "

    def build_tree(directory: Path, prefix: str = ""):
        entries = sorted(directory.iterdir(), key=lambda x: x.is_file())
        result = []
        for entry in entries:
            if entry.is_dir():
                result.append(f"{prefix}- {entry.name}")
                result.extend(build_tree(entry, prefix + indent))
            else:
                result.append(f"{prefix}- {entry.name}")
        return result

    tree.extend(build_tree(Path(root_path)))
    return "\n".join(tree)


@mcp.tool()
async def get_alerts(state: str) -> str:
    """Get weather alerts for a US state.

    Args:
        state: Two-letter US state code (e.g. CA, NY)
    """
    url = f"{NWS_API_BASE}/alerts/active/area/{state}"
    data = await make_nws_request(url)

    if not data or "features" not in data:
        return "Unable to fetch alerts or no alerts found."

    if not data["features"]:
        return "No active alerts for this state."

    alerts = [format_alert(feature) for feature in data["features"]]
    return "\n---\n".join(alerts)

@mcp.tool()
async def get_forecast(latitude: float, longitude: float) -> str:
    """Get weather forecast for a location.

    Args:
        latitude: Latitude of the location
        longitude: Longitude of the location
    """
    # First get the forecast grid endpoint
    points_url = f"{NWS_API_BASE}/points/{latitude},{longitude}"
    points_data = await make_nws_request(points_url)

    if not points_data:
        return "Unable to fetch forecast data for this location."

    # Get the forecast URL from the points response
    forecast_url = points_data["properties"]["forecast"]
    forecast_data = await make_nws_request(forecast_url)

    if not forecast_data:
        return "Unable to fetch detailed forecast."

    # Format the periods into a readable forecast
    periods = forecast_data["properties"]["periods"]
    forecasts = []
    for period in periods[:5]:  # Only show next 5 periods
        forecast = f"""
{period['name']}:
Temperature: {period['temperature']}°{period['temperatureUnit']}
Wind: {period['windSpeed']} {period['windDirection']}
Forecast: {period['detailedForecast']}
"""
        forecasts.append(forecast)

    return "\n---\n".join(forecasts)

async def make_nws_request(url: str) -> dict[str, Any] | None:
    """Make a request to the NWS API with proper error handling."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/geo+json"
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

def format_alert(feature: dict) -> str:
    """Format an alert feature into a readable string."""
    props = feature["properties"]
    return f"""
Event: {props.get('event', 'Unknown')}
Area: {props.get('areaDesc', 'Unknown')}
Severity: {props.get('severity', 'Unknown')}
Description: {props.get('description', 'No description available')}
Instructions: {props.get('instruction', 'No specific instructions provided')}
"""

# 示例资源
# @mcp.resource("greeting://{name}")
# def greet(name: str) -> str:
#     return f"Hello, {name}!"

# 启动服务
if __name__ == "__main__":
    print("Starting MCP server...")
    mcp.run()