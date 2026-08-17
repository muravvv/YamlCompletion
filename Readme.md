# YamlCompletion

This simple script performs the LLM request defined in manually written YAML file. It is more user-frendly alternative for `curl --request POST --url https://ai.provider/v1/chat/completions --data ***`.

# Usage

```bash
pip install litellm
export OPENAI_API_KEY=my_key
python YamlCompletion.py <options> MyRequest.yaml
```

For Windows also pre-built package with all libraries included is available from the [releases page](https://github.com/muravvv/YamlCompletion/releases).

## Options

| Argument                                  | Explanation                                                          |
|-------------------------------------------|----------------------------------------------------------------------|
| -m model </br> or </br> -m provider/model | Model name </br> (LiteLLM-style provider/model is also supported)    |
| -p provider                               | Model provider ([full list](https://docs.litellm.ai/docs/providers)) |
| -a api-base                               | Custom LLM API base                                                  |
| -o file                                   | Write LLM response to file                                           |

Also, some other options available. Full list can be seen by running `python YamlCompletion.py --help`.

# Yaml file format

Yaml file is sent to [litellm.completion](https://docs.litellm.ai/docs/completion/input) as is: all top-level key-value pairs are sent as parameters of the function.

Also, two special tags are added for inserting local files into requests:
* `!base64image` inserts local image file with `data:image/***;base64,` header
* `!base64file` inserts any local file as base64 text without any headers (used for audio and video data)

In this tags file path is defined relative to yaml path.

## Simple text request

```yaml
messages:
  -
    role: system
    content: |-
      You are a helpful assistant
  -
    role: user
    content: |-
      Why sky is blue?
temperature: 1.5
```

For full list of available parameters see [Litellm documentation](https://docs.litellm.ai/docs/completion/input).

## Request with image

```yaml
messages:
  -
    role: system
    content: |-
      You are a helpful assistant
  -
    role: user
    content:
      -
        type: image_url
        image_url:
          url: !base64image "city-streets.jpg"
      -
        type: text
        text: "detect person and car"
```

## Tool usage

First request:

```yaml
messages:
  -
    role: system
    content: |-
      You are a helpful assistant
  -
    role: user
    content: |-
      What's the weather like in San Francisco?
tools:
  -
     type: function
     function: 
       name: get_current_weather
       description: "Get the current weather in a given location"
       parameters:
         type: object
         properties:
           location:
             type: string
             description: "The city and state, e.g. San Francisco, CA"
           unit: 
             type: string
             enum:
               - "celsius"
               - "fahrenheit"
           required: 
             - "location"
```

And second request with tool's result:

```yaml
messages:
  -
    role: system
    content: |-
      You are a helpful assistant
  -
    role: user
    content: |-
      What's the weather like in San Francisco?
  -
    role: assistant
    tool_calls:
      -
        id: 'aDvEZ7iMIAJ6kOCjEnYCjDhtbKZjp7ku'
        type: function
        function:
          name: get_current_weather
          arguments: '{"location":"San Francisco, CA"}'
  -
    tool_call_id: 'aDvEZ7iMIAJ6kOCjEnYCjDhtbKZjp7ku'
    role: tool
    name: get_current_weather
    content: '{"location": "San Francisco", "temperature": "72", "unit": "fahrenheit"}'
tools:
  -
     type: function
     function: 
       name: get_current_weather
       description: "Get the current weather in a given location"
       parameters:
         type: object
         properties:
           location:
             type: string
             description: "The city and state, e.g. San Francisco, CA"
           unit: 
             type: string
             enum:
               - "celsius"
               - "fahrenheit"
           required: 
             - "location"
```
