// Порядок позиций (нужен для fallback, если нет data-sort-value)
const positionOrder = ['GK', 'FB', 'CB', 'DM', 'CM', 'AM', 'WG', 'ST'];

function getPositionIndex(pos) {
    const idx = positionOrder.indexOf(pos);
    return idx === -1 ? 999 : idx;
}

document.addEventListener('DOMContentLoaded', function() {
    const tables = document.querySelectorAll('table.sortable');
    tables.forEach(table => {
        const headers = table.querySelectorAll('th');
        headers.forEach((header, index) => {
            header.addEventListener('click', () => sortTable(table, index));
            header.style.cursor = 'pointer';
            header.setAttribute('data-sort-direction', 'none');
        });
        // При загрузке применяем базовую сортировку по позиции, если таблица имеет столбец "Позиция"
        applyDefaultSort(table);
    });
});

function applyDefaultSort(table) {
    const headers = table.querySelectorAll('th');
    let posIndex = -1;
    headers.forEach((th, idx) => {
        if (th.textContent.trim() === 'Позиция') {
            posIndex = idx;
        }
    });
    if (posIndex === -1) return;
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    rows.sort((a, b) => {
        // Получаем значение позиции, учитывая data-sort-value
        const aPosCell = a.children[posIndex];
        const bPosCell = b.children[posIndex];
        const aPosRaw = aPosCell.getAttribute('data-sort-value') || aPosCell.textContent.trim();
        const bPosRaw = bPosCell.getAttribute('data-sort-value') || bPosCell.textContent.trim();
        
        // Пытаемся интерпретировать как число (индекс), иначе как текстовую позицию
        let aIdx = parseInt(aPosRaw, 10);
        let bIdx = parseInt(bPosRaw, 10);
        if (isNaN(aIdx)) aIdx = getPositionIndex(aPosRaw);
        if (isNaN(bIdx)) bIdx = getPositionIndex(bPosRaw);
        
        if (aIdx !== bIdx) return aIdx - bIdx;
        
        // Вторичная сортировка: рейтинг (убывание) – предполагаем, что это 4-й столбец (индекс 3)
        const aRatingCell = a.children[3];
        const bRatingCell = b.children[3];
        const aRatingRaw = aRatingCell ? (aRatingCell.getAttribute('data-sort-value') || aRatingCell.textContent.trim()) : '0';
        const bRatingRaw = bRatingCell ? (bRatingCell.getAttribute('data-sort-value') || bRatingCell.textContent.trim()) : '0';
        const aRating = parseFloat(aRatingRaw) || 0;
        const bRating = parseFloat(bRatingRaw) || 0;
        if (aRating !== bRating) return bRating - aRating;
        
        // Третичная: возраст (возрастание) – предполагаем, что это 5-й столбец (индекс 4)
        const aAgeCell = a.children[4];
        const bAgeCell = b.children[4];
        const aAgeRaw = aAgeCell ? (aAgeCell.getAttribute('data-sort-value') || aAgeCell.textContent.trim()) : '0';
        const bAgeRaw = bAgeCell ? (bAgeCell.getAttribute('data-sort-value') || bAgeCell.textContent.trim()) : '0';
        const aAge = parseFloat(aAgeRaw) || 0;
        const bAge = parseFloat(bAgeRaw) || 0;
        return aAge - bAge;
    });
    rows.forEach(row => tbody.appendChild(row));
}

function sortTable(table, columnIndex) {
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    const header = table.querySelectorAll('th')[columnIndex];
    const headerText = header.textContent.trim();
    const currentDirection = header.getAttribute('data-sort-direction') || 'none';
    let newDirection = 'asc';
    if (currentDirection === 'asc') newDirection = 'desc';
    else if (currentDirection === 'desc') newDirection = 'none';

    // Сброс стрелок на всех заголовках
    table.querySelectorAll('th').forEach(th => {
        th.classList.remove('sort-asc', 'sort-desc');
        th.setAttribute('data-sort-direction', 'none');
    });

    if (newDirection !== 'none') {
        header.classList.add(newDirection === 'asc' ? 'sort-asc' : 'sort-desc');
        header.setAttribute('data-sort-direction', newDirection);
        rows.sort((a, b) => {
            const aCell = a.children[columnIndex];
            const bCell = b.children[columnIndex];
            // Используем data-sort-value, если есть, иначе текстовое содержимое
            let aVal = aCell.getAttribute('data-sort-value') || aCell.textContent.trim();
            let bVal = bCell.getAttribute('data-sort-value') || bCell.textContent.trim();

            if (headerText === 'Позиция') {
                // Для позиции пытаемся интерпретировать значение как число (индекс)
                let aIdx = parseInt(aVal, 10);
                let bIdx = parseInt(bVal, 10);
                if (isNaN(aIdx)) aIdx = getPositionIndex(aVal);
                if (isNaN(bIdx)) bIdx = getPositionIndex(bVal);
                aVal = aIdx;
                bVal = bIdx;
            } else {
                // Для числовых колонок пробуем парсить числа
                const aNum = parseFloat(aVal);
                const bNum = parseFloat(bVal);
                if (!isNaN(aNum) && !isNaN(bNum)) {
                    aVal = aNum;
                    bVal = bNum;
                }
            }

            let result = 0;
            if (aVal < bVal) result = -1;
            else if (aVal > bVal) result = 1;
            else {
                // Вторичная сортировка: рейтинг (убывание, колонка 3)
                const aRatingCell = a.cells[3];
                const bRatingCell = b.cells[3];
                const aRatingRaw = aRatingCell ? (aRatingCell.getAttribute('data-sort-value') || aRatingCell.textContent.trim()) : '0';
                const bRatingRaw = bRatingCell ? (bRatingCell.getAttribute('data-sort-value') || bRatingCell.textContent.trim()) : '0';
                const aRating = parseFloat(aRatingRaw) || 0;
                const bRating = parseFloat(bRatingRaw) || 0;
                if (aRating !== bRating) result = bRating - aRating;
                else {
                    // Третичная: возраст (возрастание, колонка 4)
                    const aAgeCell = a.cells[4];
                    const bAgeCell = b.cells[4];
                    const aAgeRaw = aAgeCell ? (aAgeCell.getAttribute('data-sort-value') || aAgeCell.textContent.trim()) : '0';
                    const bAgeRaw = bAgeCell ? (bAgeCell.getAttribute('data-sort-value') || bAgeCell.textContent.trim()) : '0';
                    const aAge = parseFloat(aAgeRaw) || 0;
                    const bAge = parseFloat(bAgeRaw) || 0;
                    result = aAge - bAge;
                }
                return newDirection === 'asc' ? result : -result;
            }
            return newDirection === 'asc' ? result : -result;
        });
    } else {
        // Возврат к базовой сортировке (по позиции)
        applyDefaultSort(table);
        return; // таблица уже перестроена
    }
    rows.forEach(row => tbody.appendChild(row));
}