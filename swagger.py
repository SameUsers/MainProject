def register_swagger_path(swagger):
    swagger.add_path(
        path="/authorization",
        method="post",
        summary="Авторизация пользователя",
        description="""
            Создает токен авторизации для нового пользователя.
            Принимает username, возвращает token и time_limit.
        """,
        request_body={
            "required": True,
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "username": {
                                "type": "string",
                                "example": "Victor"
                            }
                        },
                        "required": ["username"]
                    }
                }
            }
        },
        responses={
            "200": {
                "description": "Токен успешно создан",
                "content": {
                    "application/json": {
                        "example": {
                            "username": "Victor",
                            "token": "4d3fcbcb9f4f45ae9d9f9b9...",
                            "time_limit": "600"
                        }
                    }
                }
            },
            "400": {
                "description": "Ошибка в теле запроса",
                "content": {
                    "application/json": {
                        "example": {"Ошибка": "Имя для пользователя не указано"}
                    }
                }
            }
        }
    )
    
    swagger.add_path(
    path="/task",
    method="post",
    summary="Отправка аудиофайлов в очередь обработки",
    description="""
    Принимает один или несколько аудиофайлов (multipart/form-data) и ставит задачи в очередь.
    Проверяет наличие времени у пользователя, обновляет лимит и сохраняет задачи в БД.
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
            "description": "Успешная постановка задачи в очередь",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "task_id": "abc123",
                            "file_name": "audio1.wav",
                            "remaining_time": 540
                        },
                        {
                            "task_id": "def456",
                            "file_name": "audio2.wav",
                            "remaining_time": 480
                        }
                    ]
                }
            }
        },
        "400": {
            "description": "Ошибка валидации или недостаточно времени",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_format": {
                            "summary": "Неподдерживаемый формат",
                            "value": {"Ошибка": "Неподдерживаемый формат аудио"}
                        },
                        "not_enough_time": {
                            "summary": "Недостаточно времени",
                            "value": {"Ошибка": "Недостаточно времени. Осталось: 10 сек, требуется: 25 сек."}
                        },
                        "no_audio": {
                            "summary": "Аудио не найдены",
                            "value": {"Ошибка": "Ауидо не найдены"}
                        }
                    }
                }
            }
        }
    },
    security=[{"ApiTokenAuth": []}]
)
