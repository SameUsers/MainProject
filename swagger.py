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
    security=[{"ApiTokenAuth": []}])
    swagger.add_path(
    path="/status",
    method="get",
    summary="Получение статуса задач",
    description="""
    Возвращает статус задачи по task_id, либо список всех задач пользователя постранично.<br>
    Требуется заголовок Authorization с токеном.<br>
    Если передан task_id, вернёт одну задачу. Без task_id — список задач с пагинацией.
    """,
    parameters=[
        {
            "name": "Authorization",
            "in": "header",
            "required": True,
            "description": "Authorization <token>",
            "schema": {
                "type": "string",
                "example": "Authorization: 123456abcdef..."
            }
        },
        {
            "name": "task_id",
            "in": "query",
            "required": False,
            "description": "ID конкретной задачи",
            "schema": {
                "type": "string",
                "example": "abc123"
            }
        },
        {
            "name": "page",
            "in": "query",
            "required": False,
            "description": "Номер страницы для пагинации (по умолчанию 1)",
            "schema": {
                "type": "integer",
                "example": 1
            }
        }
    ],
    responses={
        "200": {
            "description": "Успешный ответ с задачами или статусом одной задачи",
            "content": {
                "application/json": {
                    "examples": {
                        "single_task": {
                            "summary": "Одна задача",
                            "value": {
                                "task_id": "abc123",
                                "file_name": "audio1.wav",
                                "status": "Completed",
                                "username": "Victor"
                            }
                        },
                        "paginated": {
                            "summary": "Список задач",
                            "value": {
                                "page": 1,
                                "per_page": 10,
                                "total_tasks": 2,
                                "total_pages": 1,
                                "tasks": [
                                    {
                                        "task_id": "abc123",
                                        "file_name": "audio1.wav",
                                        "status": "Completed"
                                    },
                                    {
                                        "task_id": "def456",
                                        "file_name": "audio2.wav",
                                        "status": "Queued"
                                    }
                                ]
                            }
                        }
                    }
                }
            }
        },
        "404": {
            "description": "Задача не найдена",
            "content": {
                "application/json": {
                    "example": {
                        "Ошибка": "Задача не найдена"
                    }
                }
            }
        }
    },
    security=[{"ApiTokenAuth": []}])
    swagger.add_path(
    path="/download",
    method="get",
    summary="Скачивание результата задачи",
    description="""
    Позволяет скачать результат обработки задачи.<br>
    Поддерживаются форматы: txt, json. <br>
    Требуется заголовок Authorization, а также query-параметры task_id и type.
    """,
    parameters=[
        {
            "name": "Authorization",
            "in": "header",
            "required": True,
            "description": "Authorization <token>",
            "schema": {
                "type": "string",
                "example": "Authorization: 123456abcdef..."
            }
        },
        {
            "name": "task_id",
            "in": "query",
            "required": True,
            "description": "ID задачи, для которой нужно скачать файл",
            "schema": {
                "type": "string",
                "example": "abc123"
            }
        },
        {
            "name": "type",
            "in": "query",
            "required": True,
            "description": "Тип файла для скачивания (`txt` или `json`)",
            "schema": {
                "type": "string",
                "enum": ["txt", "json"],
                "example": "txt"
            }
        }
    ],
    responses={
        "200": {
            "description": "Файл успешно скачан",
            "content": {
                "application/octet-stream": {
                    "schema": {
                        "type": "string",
                        "format": "binary"
                    }
                }
            }
        },
        "400": {
            "description": "Ошибка в запросе",
            "content": {
                "application/json": {
                    "examples": {
                        "missing_params": {
                            "summary": "Параметры не переданы",
                            "value": {"Ошибка": "Необходимо указать task_id и тип файла (type=txt|json)"}
                        },
                        "invalid_type": {
                            "summary": "Недопустимый тип файла",
                            "value": {"Ошибка": "Тип файла не поддерживается"}
                        }
                    }
                }
            }
        },
        "404": {
            "description": "Задача или файл не найдены",
            "content": {
                "application/json": {
                    "examples": {
                        "not_found": {
                            "summary": "Задача не найдена",
                            "value": {"Ошибка": "Задача не найдена или доступ запрещён"}
                        },
                        "file_missing": {
                            "summary": "Файл не найден",
                            "value": {"Ошибка": "Файл не найден по пути ..."}
                        }
                    }
                }
            }
        },
        "500": {
            "description": "Внутренняя ошибка сервера",
            "content": {
                "application/json": {
                    "example": {
                        "Ошибка": "Непредвиденная ошибка: <описание>"
                    }
                }
            }
        }
    },
    security=[{"ApiTokenAuth": []}]
)
