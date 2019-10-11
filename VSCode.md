VSCode instructions 

**How it works?**

Here is a VSCode setup integration example
![VSCode](docs/images/VSCode.gif)

**Install VSCode**

1. Install VS [code binary](https://code.visualstudio.com/). Here is the download [link](https://code.visualstudio.com/Download) for Windows, macOS, linux-debian.
2. Start VSCode, on macOS press CMD+&lt;SPACE&gt; and type __code__
3. Install [YAML support](https://marketplace.visualstudio.com/items?itemName=redhat.vscode-yaml) for VSCode. Here is the [github repo](https://github.com/redhat-developer/vscode-yaml)

**JSON/YAML Setup**

1. Edit "user.settings" on macOS Code -> Preferences -> Settings
2. In the search bar search for __json.schemas__ ![VS-Code-Setup](docs/images/VS-JsonSettings.png)
3. Click on __settings.json__
4. Cut-n-paste the following settings (note this is setup for US-east-1 currently, the same 
```
{
    "[yaml]": {
        "editor.insertSpaces": true,
        "editor.tabSize": 2,
        "editor.quickSuggestions": {
            "other": true,
            "comments": false,
            "strings": true
        },
        "editor.autoIndent": true
    },
    "editor.renderWhitespace": "all",
    "editor.tabSize": 2,
    "editor.autoIndent": true,
    "yaml.format.enable": true,
    "yaml.trace.server": "verbose",
    "json.schemas": [
        {
            "fileMatch": [
                "*-cfn-us-east-1.json"
            ],
            "url": "https://s3.us-east-1.amazonaws.com/cfn-resource-specifications-us-east-1-prod/schemas/2.15.0/all-spec.json"
        }
    ],
    "yaml.schemas": {
        "https://s3.amazonaws.com/cfn-resource-specifications-us-east-1-prod/schemas/2.15.0/all-spec.json": "*-us-east-1-cfn.yaml"
    }
}
```
5. Create new file with the extension specified in the mapping network-cfn-us-east-1.json, or network-cfn-us-east-1.yaml. VSCode will use the mapping to determine code assist, validate the template locally for errors

**YAML Gotchas**

YAML is very whitespace sensitive for code completion. YAML LSP support does not deal with whitespace correctly. Here are tips to follow along if code completion isn't working as desired 

1. Ensure to get rid of all white spaces below the line you are editing 
2. Remember that you _can not_ edit in between. Editing towards the end is the only one works. You still will have some partial results but experience is subpar. This is true for all json schemas
