def register_swagger_path(swagger):
    swagger.add_path(
    path="/task",
    method="post",
    summary="Отправка аудиофайлов в очередь обработки",
    description="""
    Принимает один или несколько аудиофайлов и ставит задачи в очередь на обработку.

    Требуется передать JWT-токен в заголовке:
    Authorization: Bearer <token>

    Тело запроса должно быть типа multipart/form-data, 
    где параметр audio — массив аудиофайлов.

    Поддерживаемые форматы: wav, mp3, flac
    """,
    request_body={
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "audio": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "format": "binary"
                            },
                            "description": "Один или несколько аудиофайлов"
                        }
                    },
                    "required": ["audio"]
                }
            }
        }
    },
    responses={
        "200": {
            "description": "Список успешно поставленных задач",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "task_id": "abc123",
                            "file_name": "audio1.wav",
                            "remaining_time": 120
                        },
                        {
                            "task_id": "def456",
                            "file_name": "audio2.mp3",
                            "remaining_time": 60
                        }
                    ]
                }
            }
        },
        "400": {
            "description": "Ошибка валидации, неподдерживаемый формат или недостаточно времени",
            "content": {
                "application/json": {
                    "example": {
                        "Ошибка": "Недостаточно времени. Осталось: 10 сек, требуется: 30 сек."
                    }
                }
            }
        }
    }
)    
    